"""Deterministic all-100 classification bootstrap + 50-case selection (B07 Pro).

This module is the single source of truth for the frozen
``classification_lock.json`` and ``two_step_50_manifest.json``.  Everything here
is DETERMINISTIC: no model calls, no network, no wall-clock, no filesystem
mutation beyond reading the canonical scenario descriptors + workflows.

Classification dimensions
-------------------------
* ``route`` — one of the eight two-step routes (``vibecomfy.executor.two_step
  .TWO_STEP_ROUTE_POLICIES`` keys).  Derived from the descriptor's canonical
  classification (``classification.kind`` / ``answer_rubric`` / ``_tags.
  query_type``) plus an explicit, documented bootstrap-override table for the
  routes the corpus does not naturally populate (see :data:`EXPLICIT_ROUTES`).
* ``behavior`` — derived from ``route``: edit-intent routes (``revise``,
  ``adapt``, ``reorganise``, ``requires_custom_nodes``) are ``"edit"``; the
  answer routes (``clarify``, ``respond``, ``inspect``, ``research``) are
  ``"non-edit"``.  By construction the route quotas (12+8+2+2 = 24 edit,
  2+8+8+8 = 26 non-edit) make the behavior quota exact.
* ``ledger`` — ``"in"`` when the scenario id appears in the committed
  ``scenfails57_manifest.json`` (the 57-ledger that shares billing with the
  paired comparison), else ``"out"``.
* ``graph_size`` — small (<=15 nodes), medium (16-40), large (>40), counted from
  the source workflow (``nodes`` dict, ``nodes`` list, or ComfyUI API top-level
  node map).  Graph-less descriptors default to ``"small"``.
* ``media`` — image / video / multimodal / audio / 3d / special.  Derived from
  ``_tags.modality``, falling back to the id prefix, with ``"special"`` reserved
  for graph-less descriptors (the research health control has no source graph).

Selection
---------
The 50-case selection is exact on the HARD quotas (route, behavior, ledger) and
best-fit on media/size with a documented stable-hash fallback:

1. Routes whose pool size equals their quota are forced in.
2. The remaining four routes (inspect/research/revise/adapt) allocate their
   in-57/out-57 split by enumerating every feasible allocation and picking the
   one that minimizes media+size target deviation (ties broken
   lexicographically by the allocation tuple).
3. Within a route, candidates are ordered by (media under-fill, size
   under-fill, sha256(scenario_id)) — the stable hash is the documented
   tie-break fallback.

The committed actual media/size table is recorded in ``classification_lock.json``
under ``quota_table.actual`` so any deviation from the soft targets is auditable
without re-running the selection.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

# ── route vocabulary (mirrors vibecomfy.executor.two_step.TWO_STEP_ROUTE_POLICIES)
ROUTES: tuple[str, ...] = (
    "clarify",
    "respond",
    "inspect",
    "research",
    "requires_custom_nodes",
    "revise",
    "adapt",
    "reorganise",
)
EDIT_ROUTES = frozenset({"revise", "adapt", "reorganise", "requires_custom_nodes"})
NON_EDIT_ROUTES = frozenset({"clarify", "respond", "inspect", "research"})

# ── HARD quotas (route / behavior / ledger) ──────────────────────────────────
ROUTE_QUOTA: dict[str, int] = {
    "clarify": 2,
    "respond": 8,
    "inspect": 8,
    "research": 8,
    "requires_custom_nodes": 2,
    "revise": 12,
    "adapt": 8,
    "reorganise": 2,
}
BEHAVIOR_QUOTA: dict[str, int] = {"edit": 24, "non-edit": 26}
LEDGER_QUOTA: dict[str, int] = {"in": 25, "out": 25}

# ── SOFT (best-fit) targets ───────────────────────────────────────────────────
MEDIA_TARGET: dict[str, int] = {
    "image": 13,
    "video": 14,
    "multimodal": 12,
    "audio": 5,
    "3d": 5,
    "special": 1,
}
SIZE_TARGET: dict[str, int] = {"small": 15, "medium": 20, "large": 15}

_SMALL_MAX_NODES = 15
_MEDIUM_MAX_NODES = 40

# ── Bootstrap route overrides ─────────────────────────────────────────────────
#
# The live corpus has no natural tool-free-Q&A (``respond``), clarifying-question
# (``clarify``), missing-custom-node (``requires_custom_nodes``), or layout-only
# (``reorganise``) descriptors, so those lanes are filled by an explicit,
# audited override table.  ``route_source: "explicit"`` is recorded on each
# override so the bootstrap nature stays visible.
#
# reorganise — layout-only edits (arrange/grid).
# requires_custom_nodes — edits that need a different custom node/checkpoint.
# clarify — a health control whose query explicitly asks for a clarifying
#           question, plus the vaguest diagnose descriptor.
# respond — the lightest non-edit descriptors (explain walk-throughs), re-labeled
#           as the lightweight answer lane (bootstrap approximation).
EXPLICIT_ROUTES: dict[str, str] = {
    # reorganise (2)
    "image-generates-a-2x2-seed-variation": "reorganise",
    "image-background-removal-and-grid-composition-54a681": "reorganise",
    # requires_custom_nodes (2)
    "audio-acestep-audio-generation-workflow-2a31ec": "requires_custom_nodes",
    "hotshot-16-frames-agent-edit": "requires_custom_nodes",
    # clarify (2)
    "live-graph-explanation-smoke": "clarify",
    "video-wan-video-generation-with-vace-and-multi-outpu-d1caec": "clarify",
    # respond (8)
    "multi-animated-image-to-video-with-svd-and-lora-4ed6d9": "respond",
    "multi-audio-to-image-mel-band-roformer-workflow-b22937": "respond",
    "multi-wan2-2-lightning-t2v-video-generation-with-lor-703c14": "respond",
    "video-animatediff-video-to-video-with-controlnet-and-3c978e": "respond",
    "video-image-to-video-with-svd-and-webp-output-1882aa": "respond",
    "video-inpaint-and-video-composition-with-spline-path-0c2716": "respond",
    "video-seedvr2-video-upscaling-workflow-052e59": "respond",
    "video-video-loading-and-saving-workflow-1c7ad8": "respond",
}


def _node_count(graph: Any) -> int | None:
    """Count nodes in a ComfyUI workflow (API map, litegraph, or corpus shape)."""
    if not isinstance(graph, dict):
        return None
    nodes = graph.get("nodes")
    if isinstance(nodes, dict):
        return len(nodes)
    if isinstance(nodes, list):
        return len(nodes)
    values = list(graph.values())
    if values and all(isinstance(v, dict) and "class_type" in v for v in values):
        return len(values)
    return None


def _graph_size(node_count: int | None) -> str:
    if node_count is None:
        return "small"  # graph-less descriptor (research health control)
    if node_count <= _SMALL_MAX_NODES:
        return "small"
    if node_count <= _MEDIUM_MAX_NODES:
        return "medium"
    return "large"


_ID_MEDIA_PREFIXES = (
    ("3d", "3d"),
    ("audio", "audio"),
    ("image", "image"),
    ("video", "video"),
    ("multi", "multimodal"),
)


def _media(scenario: Mapping[str, Any]) -> str:
    tags = scenario.get("_tags") or {}
    modality = tags.get("modality")
    if modality:
        return "multimodal" if modality == "multi" else str(modality)
    scenario_id = str(scenario.get("id") or "")
    for prefix, value in _ID_MEDIA_PREFIXES:
        if scenario_id.startswith(prefix + "-"):
            return value
    if not scenario.get("workflow_path") and "graph" not in scenario:
        return "special"
    return "image"


def _route_for(scenario: Mapping[str, Any]) -> tuple[str, str]:
    """Return ``(route, route_source)`` for one scenario descriptor."""
    scenario_id = str(scenario.get("id") or "")
    if scenario_id in EXPLICIT_ROUTES:
        return EXPLICIT_ROUTES[scenario_id], "explicit"

    classification = scenario.get("classification") or {}
    kind = classification.get("kind")
    tags = scenario.get("_tags") or {}
    query_type = tags.get("query_type", "")

    if kind == "health_control":
        route = "research" if scenario_id == "speed-distillation-research" else "inspect"
        return route, "health_control"
    if scenario.get("answer_rubric"):
        route = "research" if query_type == "research" else "inspect"
        return route, "query_type"
    # edit-intent descriptor (expect_graph_changed == True)
    if query_type == "big_adjustment":
        return "adapt", "query_type"
    return "revise", "query_type_default"


def classify_scenario(
    scenario: Mapping[str, Any],
    *,
    in_57_ids: frozenset[str],
    workflow_loader: Any | None = None,
) -> dict[str, Any]:
    """Classify one scenario descriptor into the five dimensions."""
    scenario_id = str(scenario.get("id") or "")
    route, route_source = _route_for(scenario)

    graph: Any = None
    if scenario.get("workflow_path"):
        path = Path(str(scenario["workflow_path"]))
        if path.is_file():
            graph = json.loads(path.read_text(encoding="utf-8"))
    elif isinstance(scenario.get("graph"), dict):
        graph = scenario["graph"]

    node_count = _node_count(graph)
    return {
        "id": scenario_id,
        "route": route,
        "route_source": route_source,
        "behavior": "edit" if route in EDIT_ROUTES else "non-edit",
        "ledger": "in" if scenario_id in in_57_ids else "out",
        "graph_size": _graph_size(node_count),
        "media": _media(scenario),
        "node_count": node_count,
    }


def _stable_key(scenario_id: str) -> str:
    """Documented stable-hash fallback for selection tie-breaks."""
    return hashlib.sha256(scenario_id.encode("utf-8")).hexdigest()


def _route_pools(lock_entries: list[dict[str, Any]]) -> dict[str, list[str]]:
    pools: dict[str, list[str]] = {route: [] for route in ROUTES}
    for entry in lock_entries:
        pools[entry["route"]].append(entry["id"])
    for route in ROUTES:
        pools[route].sort()
    return pools


def _deviation(actual: Mapping[str, int], target: Mapping[str, int]) -> int:
    return sum(abs(int(actual.get(k, 0)) - int(t)) for k, t in target.items())


def select_50(lock_entries: list[dict[str, Any]]) -> tuple[list[str], dict[str, Any]]:
    """Select the 50 cases (hard quotas exact, media/size best-fit).

    Returns ``(selected_ids, actual_quota_table)``.
    """
    by_id = {e["id"]: e for e in lock_entries}
    pools = _route_pools(lock_entries)

    # 1. Routes whose pool exactly matches their quota are forced in.
    forced: set[str] = set()
    for route in ROUTES:
        if len(pools[route]) == ROUTE_QUOTA[route]:
            forced.update(pools[route])

    remaining_routes = ["inspect", "research", "revise", "adapt"]

    forced_in = sum(1 for s in forced if by_id[s]["ledger"] == "in")
    forced_out = len(forced) - forced_in
    need_in = LEDGER_QUOTA["in"] - forced_in
    need_out = LEDGER_QUOTA["out"] - forced_out

    # Per-route in/out availability (excluding forced).
    avail: dict[str, tuple[list[str], list[str]]] = {}
    for route in remaining_routes:
        ins = [s for s in pools[route] if s not in forced and by_id[s]["ledger"] == "in"]
        outs = [s for s in pools[route] if s not in forced and by_id[s]["ledger"] == "out"]
        avail[route] = (ins, outs)

    def pick_for_allocation(alloc: dict[str, int]) -> tuple[set[str], int]:
        """Greedy within-route pick for a fixed in/out allocation."""
        selected = set(forced)
        media_counts: Counter[str] = Counter(by_id[s]["media"] for s in selected)
        size_counts: Counter[str] = Counter(by_id[s]["graph_size"] for s in selected)

        def rank(scenario_id: str) -> tuple[int, int, str]:
            media = by_id[scenario_id]["media"]
            size = by_id[scenario_id]["graph_size"]
            media_need = MEDIA_TARGET.get(media, 0) - media_counts.get(media, 0)
            size_need = SIZE_TARGET.get(size, 0) - size_counts.get(size, 0)
            return (media_need, size_need, _stable_key(scenario_id))

        for route in remaining_routes:
            ins, outs = avail[route]
            take_in = alloc[route]
            take_out = ROUTE_QUOTA[route] - take_in
            ins_sorted = sorted(ins, key=rank)
            outs_sorted = sorted(outs, key=rank)
            for scenario_id in ins_sorted[:take_in] + outs_sorted[:take_out]:
                selected.add(scenario_id)
                media_counts[by_id[scenario_id]["media"]] += 1
                size_counts[by_id[scenario_id]["graph_size"]] += 1
        return selected, _deviation(media_counts, MEDIA_TARGET) + _deviation(
            size_counts, SIZE_TARGET
        )

    # Enumerate feasible allocations (small integer space) and keep the best.
    best: tuple[tuple[int, ...], set[str], dict[str, int]] | None = None
    for insp_in in range(4, 9):
        for res_in in range(4, 9):
            for rev_in in range(0, 13):
                for adapt_in in range(6, 9):
                    if insp_in + res_in + rev_in + adapt_in != need_in:
                        continue
                    alloc = {
                        "inspect": insp_in,
                        "research": res_in,
                        "revise": rev_in,
                        "adapt": adapt_in,
                    }
                    feasible = True
                    for route in remaining_routes:
                        ins, outs = avail[route]
                        take_in = alloc[route]
                        take_out = ROUTE_QUOTA[route] - take_in
                        if take_in > len(ins) or take_out > len(outs):
                            feasible = False
                            break
                    if not feasible:
                        continue
                    selected, deviation = pick_for_allocation(alloc)
                    key = (
                        deviation,
                        insp_in,
                        res_in,
                        rev_in,
                        adapt_in,
                    )
                    if best is None or key < best[0]:
                        best = (key, selected, alloc)

    assert best is not None, "no feasible 50-case selection"
    _, selected, alloc = best

    selected_ids = sorted(selected)
    actual_quota = _actual_quota_table(by_id, selected_ids, alloc)
    return selected_ids, actual_quota


def _actual_quota_table(
    by_id: Mapping[str, dict[str, Any]],
    selected_ids: list[str],
    alloc: Mapping[str, int],
) -> dict[str, Any]:
    route_counts = Counter(by_id[s]["route"] for s in selected_ids)
    behavior_counts = Counter(by_id[s]["behavior"] for s in selected_ids)
    ledger_counts = Counter(by_id[s]["ledger"] for s in selected_ids)
    media_counts = Counter(by_id[s]["media"] for s in selected_ids)
    size_counts = Counter(by_id[s]["graph_size"] for s in selected_ids)
    return {
        "routes": {r: route_counts.get(r, 0) for r in ROUTES},
        "behavior": {b: behavior_counts.get(b, 0) for b in ("edit", "non-edit")},
        "ledger": {k: ledger_counts.get(k, 0) for k in ("in", "out")},
        "media": {k: media_counts.get(k, 0) for k in MEDIA_TARGET},
        "graph_size": {k: size_counts.get(k, 0) for k in SIZE_TARGET},
        "in_57_allocation": {k: int(v) for k, v in alloc.items()},
    }


def build_classification_lock(
    scenarios: list[Mapping[str, Any]],
    *,
    in_57_ids: frozenset[str],
) -> dict[str, Any]:
    """Classify all *scenarios* deterministically and freeze the lock payload."""
    entries = [classify_scenario(s, in_57_ids=in_57_ids) for s in scenarios]
    entries.sort(key=lambda e: e["id"])
    selected_ids, actual_quota = select_50(entries)
    return {
        "schema_version": 1,
        "scenario_count": len(entries),
        "selected_count": len(selected_ids),
        "selected_ids": selected_ids,
        "quota_table": {
            "routes": dict(ROUTE_QUOTA),
            "behavior": dict(BEHAVIOR_QUOTA),
            "ledger": dict(LEDGER_QUOTA),
            "media_target": dict(MEDIA_TARGET),
            "graph_size_target": dict(SIZE_TARGET),
            "actual": actual_quota,
        },
        "rules": {
            "behavior": "derived from route (edit = revise/adapt/reorganise/requires_custom_nodes)",
            "ledger": "in == scenario id present in scenfails57_manifest.json",
            "graph_size_thresholds": {
                "small": f"<= {_SMALL_MAX_NODES} nodes",
                "medium": f"{_SMALL_MAX_NODES + 1}-{_MEDIUM_MAX_NODES} nodes",
                "large": f"> {_MEDIUM_MAX_NODES} nodes",
                "graphless_default": "small",
            },
            "media": "modality tag -> id prefix -> special (graph-less) / image fallback",
            "stable_hash_fallback": "sha256(scenario_id) breaks selection ties",
            "explicit_route_overrides": dict(EXPLICIT_ROUTES),
        },
        "entries": entries,
    }


def build_two_step_manifest(
    lock: Mapping[str, Any],
    *,
    scenarios_dir: Path | None = None,
    manifest_path: Path | None = None,
    repo: Path | None = None,
) -> dict[str, Any]:
    """Build the strict 50/50 two-step manifest from the frozen lock.

    Reuses :func:`tests.live_agentic_harness.scenario_manifest.build_manifest`
    so descriptor/source hashes are byte-identical to the authoritative
    ``scenario_manifest.json``; only ``inclusion_status`` and the frozen
    ``classification`` block are overlaid.
    """
    from .scenario_manifest import build_manifest as _build_manifest  # noqa: PLC0415

    kwargs: dict[str, Any] = {}
    if scenarios_dir is not None:
        kwargs["scenarios_dir"] = scenarios_dir
    if repo is not None:
        kwargs["repo"] = repo
    manifest = _build_manifest(**kwargs)
    selected = set(lock["selected_ids"])
    lock_by_id = {e["id"]: e for e in lock["entries"]}
    for entry in manifest["entries"]:
        scenario_id = entry["id"]
        entry["inclusion_status"] = "included" if scenario_id in selected else "excluded"
        cls = lock_by_id[scenario_id]
        entry["classification"] = {
            "route": cls["route"],
            "route_source": cls["route_source"],
            "behavior": cls["behavior"],
            "ledger": cls["ledger"],
            "graph_size": cls["graph_size"],
            "media": cls["media"],
        }
    manifest["scenario_count"] = sum(
        1 for e in manifest["entries"] if e["inclusion_status"] == "included"
    )
    manifest["selection"] = {
        "included": len(selected),
        "excluded": len(manifest["entries"]) - len(selected),
        "quota_table": lock["quota_table"],
    }
    return manifest


# ── lock / manifest validation ───────────────────────────────────────────────


class ClassificationError(ValueError):
    """Raised when the frozen lock/manifest is internally inconsistent."""


def validate_lock(
    lock: Mapping[str, Any],
    *,
    scenario_ids: frozenset[str],
    in_57_ids: frozenset[str],
) -> None:
    """Validate a classification lock against the canonical descriptor set."""
    if lock.get("schema_version") != 1:
        raise ClassificationError("lock schema_version must be 1")
    entries = lock.get("entries")
    if not isinstance(entries, list) or len(entries) != len(scenario_ids):
        raise ClassificationError("lock must classify exactly the canonical scenarios")
    lock_ids = {e.get("id") for e in entries}
    if lock_ids != set(scenario_ids):
        raise ClassificationError(
            f"lock id set mismatch: missing={sorted(set(scenario_ids) - lock_ids)}, "
            f"extra={sorted(lock_ids - set(scenario_ids))}"
        )
    for entry in entries:
        for field in ("route", "behavior", "ledger", "graph_size", "media"):
            if not entry.get(field):
                raise ClassificationError(f"lock entry {entry.get('id')!r} missing {field}")
        if entry["route"] not in ROUTES:
            raise ClassificationError(f"lock entry {entry.get('id')!r} bad route {entry['route']!r}")
        if entry["behavior"] not in {"edit", "non-edit"}:
            raise ClassificationError(f"lock entry {entry.get('id')!r} bad behavior")
        expected_behavior = "edit" if entry["route"] in EDIT_ROUTES else "non-edit"
        if entry["behavior"] != expected_behavior:
            raise ClassificationError(
                f"lock entry {entry.get('id')!r} behavior/route mismatch"
            )
        if entry["ledger"] not in {"in", "out"}:
            raise ClassificationError(f"lock entry {entry.get('id')!r} bad ledger")
        expected_ledger = "in" if entry["id"] in in_57_ids else "out"
        if entry["ledger"] != expected_ledger:
            raise ClassificationError(f"lock entry {entry.get('id')!r} ledger mismatch")


def validate_manifest_quotas(manifest: Mapping[str, Any], lock: Mapping[str, Any]) -> None:
    """Validate the 50-manifest selection against the lock's hard quotas."""
    lock_by_id = {e["id"]: e for e in lock["entries"]}
    included = [e["id"] for e in manifest["entries"] if e["inclusion_status"] == "included"]
    if len(included) != 50:
        raise ClassificationError(f"manifest must include 50 scenarios, got {len(included)}")

    route_counts = Counter(lock_by_id[s]["route"] for s in included)
    for route, quota in ROUTE_QUOTA.items():
        if route_counts.get(route, 0) != quota:
            raise ClassificationError(
                f"route quota {route}: expected {quota}, got {route_counts.get(route, 0)}"
            )
    behavior_counts = Counter(lock_by_id[s]["behavior"] for s in included)
    for behavior, quota in BEHAVIOR_QUOTA.items():
        if behavior_counts.get(behavior, 0) != quota:
            raise ClassificationError(
                f"behavior quota {behavior}: expected {quota}, got {behavior_counts.get(behavior, 0)}"
            )
    ledger_counts = Counter(lock_by_id[s]["ledger"] for s in included)
    for ledger, quota in LEDGER_QUOTA.items():
        if ledger_counts.get(ledger, 0) != quota:
            raise ClassificationError(
                f"ledger quota {ledger}: expected {quota}, got {ledger_counts.get(ledger, 0)}"
            )
