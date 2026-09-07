"""Source-layout helpers for live agentic workflow fixtures."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def is_litegraph_ui_graph(graph: Any) -> bool:
    return isinstance(graph, dict) and isinstance(graph.get("nodes"), list)


def has_layout_positions(graph: Mapping[str, Any]) -> bool:
    nodes = graph.get("nodes")
    return isinstance(nodes, list) and any(
        isinstance(node, Mapping) and isinstance(node.get("pos"), list)
        for node in nodes
    )


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON file must contain an object: {path}")
    return data


def _normalize_pos_or_size(value: Any) -> Any:
    if isinstance(value, Mapping) and 0 in value and 1 in value:
        return [value[0], value[1]]
    if isinstance(value, Mapping) and "0" in value and "1" in value:
        return [value["0"], value["1"]]
    return value


def _normalize_litegraph_node(node: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(node)
    if "pos" in out:
        out["pos"] = _normalize_pos_or_size(out["pos"])
    if "size" in out:
        out["size"] = _normalize_pos_or_size(out["size"])
    return out


def _ui_graph_from_corpus_record(corpus: Mapping[str, Any]) -> dict[str, Any] | None:
    nodes_payload = corpus.get("nodes")
    if not isinstance(nodes_payload, Mapping):
        return None

    nodes: list[dict[str, Any]] = []
    by_id: dict[Any, dict[str, Any]] = {}
    for node_id, node in nodes_payload.items():
        if not isinstance(node, Mapping):
            continue
        metadata = node.get("metadata")
        ui_node = metadata.get("_ui") if isinstance(metadata, Mapping) else None
        if not isinstance(ui_node, Mapping):
            continue
        item = _normalize_litegraph_node(dict(ui_node))
        item.setdefault("id", int(node_id) if str(node_id).isdigit() else node_id)
        item.setdefault("type", node.get("class_type"))
        nodes.append(item)
        by_id[item.get("id")] = item

    if not nodes or not has_layout_positions({"nodes": nodes}):
        return None

    output_links: dict[Any, tuple[Any, int]] = {}
    for node in nodes:
        for index, output in enumerate(node.get("outputs") or []):
            if not isinstance(output, Mapping):
                continue
            links = output.get("links")
            if not isinstance(links, list):
                continue
            for link_id in links:
                output_links[link_id] = (node.get("id"), int(output.get("slot_index", index) or index))

    links: list[list[Any]] = []
    seen: set[Any] = set()
    for node in nodes:
        for index, input_slot in enumerate(node.get("inputs") or []):
            if not isinstance(input_slot, Mapping):
                continue
            link_id = input_slot.get("link")
            if link_id is None or link_id in seen or link_id not in output_links:
                continue
            origin_id, origin_slot = output_links[link_id]
            target_slot = int(input_slot.get("slot_index", index) or index)
            links.append([
                link_id,
                origin_id,
                origin_slot,
                node.get("id"),
                target_slot,
                input_slot.get("type", ""),
            ])
            seen.add(link_id)

    return {
        "id": corpus.get("id"),
        "version": 0.4,
        "nodes": nodes,
        "links": links,
        "groups": [],
        "extra": {
            "vibecomfy": {
                "demo_layout_source": "corpus_ui_metadata",
                "source_id": corpus.get("id"),
            }
        },
    }


def resolve_corpus_record_path(workflow_path: str | Path, *, root: Path | None = None) -> Path | None:
    root = root or repo_root()
    path = Path(workflow_path)
    if not path.is_absolute():
        path = root / path
    try:
        rel = path.resolve().relative_to(root.resolve())
    except ValueError:
        return None

    parts = rel.parts
    name = path.name
    tracked_corpus = root / "tests" / "fixtures" / "live_agentic_corpus" / "corpus" / name
    tracked_flat = root / "tests" / "fixtures" / "live_agentic_corpus" / name
    if len(parts) >= 3 and parts[0] == "external_workflows" and parts[1] == "corpus":
        if tracked_corpus.is_file():
            return tracked_corpus
        if tracked_flat.is_file():
            return tracked_flat
        return path if path.is_file() else None
    if (
        len(parts) >= 3
        and parts[0] == "tests"
        and parts[1] == "fixtures"
        and parts[2] == "live_agentic_corpus"
    ):
        if path.is_file():
            return path
        if tracked_corpus.is_file():
            return tracked_corpus
        candidate = root / "external_workflows" / "corpus" / name
        return candidate if candidate.is_file() else None
    return None


def resolve_source_ui_path(workflow_path: str | Path, *, root: Path | None = None) -> Path | None:
    resolved = load_source_ui_graph(workflow_path, root=root)
    return resolved[0] if resolved is not None else None


def load_source_ui_graph(
    workflow_path: str | Path,
    *,
    root: Path | None = None,
) -> tuple[Path, dict[str, Any]] | None:
    root = root or repo_root()
    path = Path(workflow_path)
    if not path.is_absolute():
        path = root / path
    if path.is_file():
        graph = load_json(path)
        if is_litegraph_ui_graph(graph) and has_layout_positions(graph):
            return path, graph

    corpus_path = resolve_corpus_record_path(workflow_path, root=root)
    if corpus_path is None or not corpus_path.is_file():
        return None
    corpus = load_json(corpus_path)
    if is_litegraph_ui_graph(corpus) and has_layout_positions(corpus):
        return corpus_path, corpus
    source = corpus.get("source")
    if not isinstance(source, Mapping):
        reconstructed = _ui_graph_from_corpus_record(corpus)
        return (corpus_path, reconstructed) if reconstructed is not None else None
    source_path = source.get("path")
    if isinstance(source_path, str) and source_path:
        resolved = Path(source_path)
        if not resolved.is_absolute():
            resolved = root / resolved
        if resolved.is_file():
            graph = load_json(resolved)
            if is_litegraph_ui_graph(graph) and has_layout_positions(graph):
                return resolved, graph
    reconstructed = _ui_graph_from_corpus_record(corpus)
    return (corpus_path, reconstructed) if reconstructed is not None else None


def overlay_candidate_on_source(
    source_ui: Mapping[str, Any],
    candidate_ui: Mapping[str, Any],
) -> dict[str, Any]:
    """Return source UI with candidate node/link edits overlaid by node id.

    The compact live-agentic API fixtures are derived from the source workflow
    by removing notes, preview branches, Get/Set groups, and similar editor
    structure. For visual preview we keep the full source canvas, replace any
    nodes present in the candidate graph, preserve source positions/sizes for
    those nodes, and merge links without duplicating target inputs.
    """
    out = copy.deepcopy(dict(source_ui))
    out_nodes = out.setdefault("nodes", [])
    if not isinstance(out_nodes, list):
        out_nodes = []
        out["nodes"] = out_nodes
    source_nodes = [
        node for node in out_nodes
        if isinstance(node, dict) and node.get("id") is not None
    ]
    source_by_id = {node.get("id"): node for node in source_nodes}
    candidate_nodes = [
        node for node in candidate_ui.get("nodes", [])
        if isinstance(node, Mapping) and node.get("id") is not None
    ]

    for candidate_node in candidate_nodes:
        node_id = candidate_node.get("id")
        replacement = copy.deepcopy(dict(candidate_node))
        source_node = source_by_id.get(node_id)
        if isinstance(source_node, Mapping):
            for key in ("pos", "size"):
                if key in source_node:
                    replacement[key] = copy.deepcopy(source_node[key])
        if node_id in source_by_id:
            source_by_id[node_id].clear()
            source_by_id[node_id].update(replacement)
        else:
            out_nodes.append(replacement)
            source_by_id[node_id] = replacement

    candidate_links = [
        copy.deepcopy(link)
        for link in candidate_ui.get("links", [])
        if isinstance(link, list) and len(link) >= 5
    ]
    candidate_link_ids = {link[0] for link in candidate_links}
    occupied_targets = {(link[3], link[4]) for link in candidate_links}
    merged_links = list(candidate_links)
    for link in source_ui.get("links", []):
        if not isinstance(link, list) or len(link) < 5:
            continue
        if link[0] in candidate_link_ids:
            continue
        if (link[3], link[4]) in occupied_targets:
            continue
        merged_links.append(copy.deepcopy(link))
    out["links"] = merged_links

    extra = out.setdefault("extra", {})
    if isinstance(extra, dict):
        vibe = extra.setdefault("vibecomfy", {})
        if isinstance(vibe, dict):
            vibe["demo_layout_source"] = "source_ui_overlay"
    return out
