"""Global section placement planning for the reorganise compiler.

This module owns section-level geometry: semantic wall lanes, topology ranks,
bands, and deterministic section coordinates. Node packing remains in
``compile.py`` and is supplied as an explicit size-estimation callback.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from vibecomfy.identity.uid import make_uid

from .graph_facts import GraphInventoryFacts, NodeFurnitureFact
from .plan_types import (
    ROLE_HINT_HELPER,
    ROLE_HINT_UI,
    ROLE_HINT_UTILITY,
    SECTION_KIND_BRANCH,
    SECTION_KIND_CONDITIONING,
    SECTION_KIND_CONTAINER,
    SECTION_KIND_CONTROL,
    SECTION_KIND_CUSTOM,
    SECTION_KIND_DECODE,
    SECTION_KIND_LATENT,
    SECTION_KIND_LOADERS,
    SECTION_KIND_OUTPUT,
    SECTION_KIND_POSTPROCESS,
    SECTION_KIND_SAMPLING,
    SECTION_KIND_UTILITY,
    CanonicalNodeRef,
    LayoutPlanV1,
    RoleHint,
    SectionKind,
)

_SECTION_MIN_RANKS: Mapping[SectionKind, int] = {
    SECTION_KIND_LOADERS: 0,
    SECTION_KIND_CONDITIONING: 1,
    SECTION_KIND_LATENT: 1,
    SECTION_KIND_CONTROL: 2,
    SECTION_KIND_SAMPLING: 3,
    SECTION_KIND_BRANCH: 3,
    SECTION_KIND_DECODE: 4,
    SECTION_KIND_POSTPROCESS: 5,
    SECTION_KIND_OUTPUT: 6,
    SECTION_KIND_UTILITY: 2,
    SECTION_KIND_CONTAINER: 0,
    SECTION_KIND_CUSTOM: 2,
}


class _LayoutOptions(Protocol):
    preserve_node_sizes: bool
    minimize_setget_helpers: bool


@dataclass(frozen=True, slots=True)
class CompiledSectionTopology:
    section_id: str
    scope_path: str
    island_index: int
    rank: int
    scc_id: str
    auto_name: str
    predecessor_ids: tuple[str, ...] = ()
    successor_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "predecessor_ids", tuple(self.predecessor_ids))
        object.__setattr__(self, "successor_ids", tuple(self.successor_ids))

    def to_json(self) -> dict[str, Any]:
        return {
            "section_id": self.section_id,
            "scope_path": self.scope_path,
            "island_index": self.island_index,
            "rank": self.rank,
            "scc_id": self.scc_id,
            "auto_name": self.auto_name,
            "predecessor_ids": list(self.predecessor_ids),
            "successor_ids": list(self.successor_ids),
        }


@dataclass(frozen=True, slots=True)
class _Spacing:
    section_gap_x: int
    island_gap_x: int
    band_gap_y: int
    section_gap_y: int
    node_gap_y: int
    group_padding: int


@dataclass(frozen=True, slots=True)
class _CompileSection:
    id: str
    kind: SectionKind
    title: str
    role_hint: RoleHint | None
    node_refs: tuple[CanonicalNodeRef, ...]
    parent_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_refs", tuple(self.node_refs))


@dataclass(frozen=True, slots=True)
class _SectionPlacement:
    rank: int
    band: int
    row: int
    x: int
    y: int


_SectionSizeEstimator = Callable[
    [
        _CompileSection,
        GraphInventoryFacts,
        Mapping[CanonicalNodeRef, NodeFurnitureFact],
        _LayoutOptions,
        _Spacing,
        LayoutPlanV1 | None,
    ],
    tuple[int, int],
]


class _SectionReflow(Protocol):
    def __call__(
        self,
        placements: dict[str, _SectionPlacement],
        sections: Sequence[_CompileSection],
        topology_by_section: Mapping[str, CompiledSectionTopology],
        facts: GraphInventoryFacts,
        furniture_by_ref: Mapping[CanonicalNodeRef, NodeFurnitureFact],
        options: _LayoutOptions,
        spacing: _Spacing,
        plan: LayoutPlanV1 | None,
        estimate_section_size: _SectionSizeEstimator,
    ) -> dict[str, _SectionPlacement]: ...


def plan_section_placements(
    sections: Sequence[_CompileSection],
    section_topologies: Sequence[CompiledSectionTopology],
    facts: GraphInventoryFacts,
    spacing: _Spacing,
    furniture_by_ref: Mapping[CanonicalNodeRef, NodeFurnitureFact],
    options: _LayoutOptions,
    plan: LayoutPlanV1 | None,
    *,
    estimate_section_size: _SectionSizeEstimator,
    is_large_workflow: Callable[[GraphInventoryFacts], bool],
    reflow_overtall_lane_trails: _SectionReflow,
) -> dict[str, _SectionPlacement]:
    topology_by_section = {
        topology.section_id: topology for topology in section_topologies
    }
    huge_mode = is_large_workflow(facts)
    effective_ranks = (
        _wall_section_ranks(sections)
        if huge_mode
        else _effective_section_ranks(sections, section_topologies)
    )
    raw_band_by_section = {
        section.id: (
            _huge_wall_band(section) if huge_mode else _section_band(section, facts)
        )
        for section in sections
    }
    band_y_offsets = _band_y_offsets(
        sections,
        topology_by_section,
        effective_ranks,
        raw_band_by_section,
        facts,
        furniture_by_ref,
        options,
        spacing,
        plan,
        estimate_section_size,
        collapse_islands=huge_mode,
    )
    rank_x_offsets = _rank_x_offsets(
        sections,
        topology_by_section,
        effective_ranks,
        facts,
        furniture_by_ref,
        options,
        spacing,
        plan,
        estimate_section_size,
        collapse_islands=huge_mode,
    )
    next_y_by_lane: dict[tuple[str, int, int, int], int] = {}
    row_by_lane: dict[tuple[str, int, int, int], int] = {}
    x_by_lane: dict[tuple[str, int, int, int], int] = {}
    placed_lanes: list[tuple[str, int, int, int, int, int, int]] = []
    placements: dict[str, _SectionPlacement] = {}
    ordered_sections = sorted(
        sections,
        key=lambda item: (
            _topology_for(item, topology_by_section).scope_path,
            _topology_for(item, topology_by_section).island_index,
            effective_ranks[item.id],
            raw_band_by_section[item.id],
            *_section_semantic_sort_key(item),
        ),
    )
    lane_vertical_intervals: dict[tuple[str, int, int, int], list[tuple[int, int]]] = {}
    if huge_mode:
        preview_next_y_by_lane: dict[tuple[str, int, int, int], int] = {}
        for section in ordered_sections:
            topology = _topology_for(section, topology_by_section)
            island_index = 0
            rank = effective_ranks[section.id]
            band = raw_band_by_section[section.id]
            lane = (topology.scope_path, island_index, rank, band)
            base_y = band_y_offsets[(topology.scope_path, island_index, band)]
            y = base_y + preview_next_y_by_lane.get(lane, 0)
            _width, height = estimate_section_size(
                section,
                facts,
                furniture_by_ref,
                options,
                spacing,
                plan,
            )
            lane_vertical_intervals.setdefault(lane, []).append((y, y + height))
            preview_next_y_by_lane[lane] = (
                preview_next_y_by_lane.get(lane, 0) + height + spacing.section_gap_y
            )

    for section in ordered_sections:
        topology = _topology_for(section, topology_by_section)
        island_index = 0 if huge_mode else topology.island_index
        rank = effective_ranks[section.id]
        band = raw_band_by_section[section.id]
        lane = (topology.scope_path, island_index, rank, band)
        row = row_by_lane.get(lane, 0)
        base_y = band_y_offsets[(topology.scope_path, island_index, band)]
        y = base_y + next_y_by_lane.get(lane, 0)
        section_width, section_height = estimate_section_size(
            section,
            facts,
            furniture_by_ref,
            options,
            spacing,
            plan,
        )
        if lane in x_by_lane:
            x = x_by_lane[lane]
        elif huge_mode:
            # Pack the whole semantic lane against the contour of earlier
            # ranks, then keep every section in that lane on one straight x.
            # A lane may tuck beside a wide lower group only when none of its
            # vertical intervals reaches that group.
            x = _compact_wall_lane_x(
                placed_lanes,
                scope_path=topology.scope_path,
                island_index=island_index,
                rank=rank,
                vertical_intervals=lane_vertical_intervals[lane],
                fallback=rank_x_offsets[(topology.scope_path, island_index, rank)],
                gap_x=spacing.section_gap_x,
            )
            x_by_lane[lane] = x
        else:
            x = rank_x_offsets[(topology.scope_path, island_index, rank)]
            x_by_lane[lane] = x
        placements[section.id] = _SectionPlacement(
            rank=rank, band=band, row=row, x=x, y=y
        )
        placed_lanes.append(
            (
                topology.scope_path,
                island_index,
                rank,
                x,
                y,
                section_width,
                section_height,
            )
        )
        next_y_by_lane[lane] = (
            next_y_by_lane.get(lane, 0) + section_height + spacing.section_gap_y
        )
        row_by_lane[lane] = row + 1
    if huge_mode:
        placements = reflow_overtall_lane_trails(
            placements,
            sections,
            topology_by_section,
            facts,
            furniture_by_ref,
            options,
            spacing,
            plan,
            estimate_section_size,
        )
    return placements


def _reflow_overtall_lane_trails(
    placements: dict[str, _SectionPlacement],
    sections: Sequence[_CompileSection],
    topology_by_section: Mapping[str, CompiledSectionTopology],
    facts: GraphInventoryFacts,
    furniture_by_ref: Mapping[CanonicalNodeRef, NodeFurnitureFact],
    options: _LayoutOptions,
    spacing: _Spacing,
    plan: LayoutPlanV1 | None,
    estimate_section_size: _SectionSizeEstimator,
) -> dict[str, _SectionPlacement]:
    """Flow the trailing sections of an over-tall wall lane into a footer row.

    A resource lane (loaders, settings, model pickers) often holds many small
    sections that stack into a column far taller than the rest of the wall,
    leaving an empty band beside them.  When a lane runs well past the wall's
    main content line, its trailing sections are relaid as a left-to-right row
    anchored where the stack would have continued, so the tail fills the empty
    band instead of stretching the canvas.  Only trailing sections beyond the
    content line move; earlier sections keep their stacked positions.  The rule
    keys off lane heights and footprints, never off node or section identity.
    """
    items: list[dict[str, Any]] = []
    for section in sections:
        placement = placements[section.id]
        topology = topology_by_section[section.id]
        lane_key = (topology.scope_path, placement.rank, placement.band)
        width, height = estimate_section_size(
            section, facts, furniture_by_ref, options, spacing, plan
        )
        items.append(
            {
                "id": section.id,
                "lane": lane_key,
                "x": placement.x,
                "y": placement.y,
                "w": width,
                "h": height,
                "placement": placement,
            }
        )
    lane_bottoms: dict[tuple[str, int, int], int] = {}
    for item in items:
        lane_bottoms[item["lane"]] = max(
            lane_bottoms.get(item["lane"], 0), item["y"] + item["h"]
        )
    if len(lane_bottoms) < 2:
        return placements
    content_bottom = sorted(lane_bottoms.values(), reverse=True)[1]
    gap_x = max(spacing.section_gap_x, spacing.node_gap_y)
    for lane, bottom in lane_bottoms.items():
        if bottom <= content_bottom * 1.25:
            continue
        lane_items = [item for item in items if item["lane"] == lane]
        trailing = sorted(
            (item for item in lane_items if item["y"] + item["h"] > content_bottom),
            key=lambda item: (item["y"], item["x"]),
        )
        if len(trailing) < 2:
            continue
        anchor_y = trailing[0]["y"]
        cursor_x = min(item["x"] for item in lane_items)
        for item in trailing:
            placement = item["placement"]
            placements[item["id"]] = _SectionPlacement(
                rank=placement.rank,
                band=placement.band,
                row=placement.row,
                x=cursor_x,
                y=anchor_y,
            )
            cursor_x += item["w"] + gap_x
    return placements


def _compact_wall_lane_x(
    placed_lanes: Sequence[tuple[str, int, int, int, int, int, int]],
    *,
    scope_path: str,
    island_index: int,
    rank: int,
    vertical_intervals: Sequence[tuple[int, int]],
    fallback: int,
    gap_x: int,
) -> int:
    """Pack a huge-workflow rank against the actual vertical skyline.

    A single max-width column is too conservative for the Comfy wall layout:
    wide helper/settings groups lower in the left resource column should not
    force prompt/sampling groups on the top row far to the right. This keeps
    left-to-right rank order while only reserving horizontal space for earlier
    ranks that overlap any vertical interval occupied by the current lane.
    Treating the lane as the unit of placement keeps its sections aligned in a
    straight column; the lane only dovetails when the entire column fits.
    """
    overlapping_right_edges = [
        placed_x + placed_width + gap_x
        for (
            placed_scope,
            placed_island,
            placed_rank,
            placed_x,
            placed_y,
            placed_width,
            placed_height,
        ) in placed_lanes
        if placed_scope == scope_path
        and placed_island == island_index
        and placed_rank < rank
        and any(
            _vertical_intervals_overlap(y1, y2, placed_y, placed_y + placed_height)
            for y1, y2 in vertical_intervals
        )
    ]
    if not overlapping_right_edges:
        return fallback
    return min(fallback, max(overlapping_right_edges))


def _vertical_intervals_overlap(a1: int, a2: int, b1: int, b2: int) -> bool:
    return a1 < b2 and b1 < a2


def _wall_section_ranks(sections: Sequence[_CompileSection]) -> dict[str, int]:
    return {section.id: _wall_section_rank(section) for section in sections}


def _wall_section_rank(section: _CompileSection) -> int:
    """Semantic left-to-right ranks for huge Comfy workflow walls.

    Huge workflows are easier to read when broad functional groups form columns:
    resources/settings on the left, then conditioning, latent/sampling, decode,
    and output. Topology still informs local node ordering inside each group, but
    the group wall follows the visual convention users expect in shared Comfy
    graphs.
    """
    # Generated wall buckets carry a stronger semantic signal than their
    # human-facing title.  Consult that stable identity first: for example,
    # ``root__custom__displays`` is a conditioning-side support section, but
    # its title "Displays / Labels" used to hit the generic ``"label"`` title
    # rule and get sent to the far-right notes rank.
    bucket_id = _wall_bucket_id_from_section_id(section.id)
    if bucket_id in {
        "models",
        "clip",
        "vae",
        "lora",
        "input",
        "settings",
        "model_patching",
        "video_io",
    }:
        return 0
    if bucket_id in {"prompt", "conditioning", "displays"}:
        return 1
    if bucket_id == "labels":
        return 7
    if bucket_id == "setget":
        return 0
    if bucket_id in {"custom", "prep", "imageprep", "latent", "loop_control"}:
        return 2
    if bucket_id in {"sampling_settings", "samplers", "video_generation"}:
        return 3
    if bucket_id in {"upscale", "postprocess", "color_match", "cleanup"}:
        return 5

    title = (section.title or "").lower()
    if "input" in title or "setting" in title or "model" in title or "lora" in title:
        return 0
    if "prompt" in title or "conditioning" in title or "enhance" in title:
        return 1
    if "latent" in title or "prepare" in title:
        return 2
    if "first" in title and "sampler" in title:
        return 3
    if "sampler" in title or "sampling" in title or "optional" in title:
        return 4
    if "decode" in title or "postprocess" in title:
        return 5
    if "output" in title or "save" in title:
        return 6
    if "set / get helpers" in title:
        return 0
    if "label" in title or "note" in title:
        return 7
    if section.kind == SECTION_KIND_OUTPUT or "output" in title or "save" in title:
        return 6
    if section.kind in {SECTION_KIND_DECODE, SECTION_KIND_POSTPROCESS}:
        return 5
    if section.kind in {SECTION_KIND_SAMPLING, SECTION_KIND_BRANCH}:
        return 3
    if section.kind in {SECTION_KIND_LATENT, SECTION_KIND_CONTROL}:
        return 2
    if section.kind == SECTION_KIND_CONDITIONING:
        return 1
    if section.kind == SECTION_KIND_CUSTOM:
        return 1
    if section.kind in {
        SECTION_KIND_LOADERS,
        SECTION_KIND_UTILITY,
        SECTION_KIND_CONTAINER,
    }:
        return 0
    return 1


def _huge_wall_band(section: _CompileSection) -> int:
    bucket_id = _wall_bucket_id_from_section_id(section.id)
    # As with wall rank, generated bucket identity must win over ambiguous
    # presentation text.  "Displays / Labels" belongs in the main flow band;
    # only the dedicated labels/notes bucket is a footer band.
    if bucket_id == "setget":
        return 0
    if bucket_id == "labels":
        return 1
    if bucket_id:
        return 0
    title = (section.title or "").lower()
    if "set / get" in title or "helper" in title:
        return 0
    if "label" in title or "note" in title:
        return 1
    return 0


def _wall_bucket_id_from_section_id(section_id: str) -> str:
    if "__" not in section_id:
        return ""
    bucket_id = section_id.rsplit("__", 1)[1]
    return re.sub(r"_\d+$", "", bucket_id)


def _fixed_band_y_offsets(
    sections: Sequence[_CompileSection],
    topology_by_section: Mapping[str, CompiledSectionTopology],
    raw_band_by_section: Mapping[str, int],
    spacing: _Spacing,
) -> dict[tuple[str, int, int], int]:
    bands_by_island: dict[tuple[str, int], set[int]] = {}
    for section in sections:
        topology = _topology_for(section, topology_by_section)
        bands_by_island.setdefault(
            (topology.scope_path, topology.island_index), set()
        ).add(raw_band_by_section[section.id])

    offsets: dict[tuple[str, int, int], int] = {}
    for island_key, bands in sorted(bands_by_island.items()):
        for index, band in enumerate(sorted(bands)):
            offsets[(*island_key, band)] = index * spacing.band_gap_y
    return offsets


def _rank_x_offsets(
    sections: Sequence[_CompileSection],
    topology_by_section: Mapping[str, CompiledSectionTopology],
    effective_ranks: Mapping[str, int],
    facts: GraphInventoryFacts,
    furniture_by_ref: Mapping[CanonicalNodeRef, NodeFurnitureFact],
    options: _LayoutOptions,
    spacing: _Spacing,
    plan: LayoutPlanV1 | None,
    estimate_section_size: _SectionSizeEstimator,
    *,
    collapse_islands: bool,
) -> dict[tuple[str, int, int], int]:
    rank_widths_by_island: dict[tuple[str, int], dict[int, int]] = {}
    for section in sections:
        topology = _topology_for(section, topology_by_section)
        island_index = 0 if collapse_islands else topology.island_index
        rank = effective_ranks[section.id]
        estimated_width, _estimated_height = estimate_section_size(
            section,
            facts,
            furniture_by_ref,
            options,
            spacing,
            plan,
        )
        rank_widths = rank_widths_by_island.setdefault(
            (topology.scope_path, island_index),
            {},
        )
        rank_widths[rank] = max(rank_widths.get(rank, 0), estimated_width)

    offsets: dict[tuple[str, int, int], int] = {}
    island_base_x = 0
    for island_key, rank_widths in sorted(rank_widths_by_island.items()):
        x = island_base_x
        for rank in sorted(rank_widths):
            offsets[(*island_key, rank)] = x
            x += rank_widths[rank] + spacing.section_gap_x
        island_base_x = x + spacing.island_gap_x
    return offsets


def _effective_section_ranks(
    sections: Sequence[_CompileSection],
    section_topologies: Sequence[CompiledSectionTopology],
) -> dict[str, int]:
    topology_by_section = {
        topology.section_id: topology for topology in section_topologies
    }
    scc_members: dict[str, list[_CompileSection]] = {}
    for section in sections:
        topology = _topology_for(section, topology_by_section)
        scc_members.setdefault(topology.scc_id, []).append(section)

    rank_by_scc: dict[str, int] = {}
    for scc_id, members in sorted(scc_members.items()):
        rank_by_scc[scc_id] = max(
            max(
                topology_by_section.get(
                    member.id,
                    CompiledSectionTopology(
                        member.id,
                        _common_scope(member.node_refs),
                        0,
                        0,
                        scc_id,
                        member.id,
                    ),
                ).rank,
                _SECTION_MIN_RANKS.get(
                    member.kind, _SECTION_MIN_RANKS[SECTION_KIND_CUSTOM]
                ),
            )
            for member in members
        )

    scc_edges: dict[str, set[str]] = {scc_id: set() for scc_id in scc_members}
    for topology in section_topologies:
        for successor_id in topology.successor_ids:
            successor = topology_by_section.get(successor_id)
            if successor is None or successor.scc_id == topology.scc_id:
                continue
            scc_edges.setdefault(topology.scc_id, set()).add(successor.scc_id)
            scc_edges.setdefault(successor.scc_id, set())

    for _iteration in range(len(scc_edges) + 1):
        changed = False
        for source_scc in sorted(scc_edges, key=_id_sort_key):
            source_rank = rank_by_scc.get(source_scc, 0)
            for target_scc in sorted(scc_edges[source_scc], key=_id_sort_key):
                target_rank = rank_by_scc.get(target_scc, 0)
                if target_rank < source_rank + 1:
                    rank_by_scc[target_scc] = source_rank + 1
                    changed = True
        if not changed:
            break

    return {
        section.id: rank_by_scc[_topology_for(section, topology_by_section).scc_id]
        for section in sections
    }


def _topology_for(
    section: _CompileSection,
    topology_by_section: Mapping[str, CompiledSectionTopology],
) -> CompiledSectionTopology:
    topology = topology_by_section.get(section.id)
    if topology is not None:
        return topology
    return CompiledSectionTopology(
        section_id=section.id,
        scope_path=_common_scope(section.node_refs),
        island_index=0,
        rank=0,
        scc_id=section.id,
        auto_name=_stable_auto_name(section, section.id),
    )


def _section_band(section: _CompileSection, facts: GraphInventoryFacts) -> int:
    if _is_model_pipe_section(section, facts):
        return -1
    if section.kind in {
        SECTION_KIND_UTILITY,
        SECTION_KIND_CUSTOM,
    } or section.role_hint in {
        ROLE_HINT_HELPER,
        ROLE_HINT_UI,
        ROLE_HINT_UTILITY,
    }:
        return 1
    return 0


def _is_model_pipe_section(
    section: _CompileSection, facts: GraphInventoryFacts
) -> bool:
    if section.kind != SECTION_KIND_LOADERS:
        return False
    canonical_by_ref = {fact.ref: fact for fact in facts.canonical_refs}
    for ref in section.node_refs:
        fact = canonical_by_ref.get(ref)
        class_type = str(getattr(fact, "class_type", "")).lower()
        if any(
            token in class_type
            for token in ("checkpoint", "clip", "lora", "unet", "vae", "model")
        ):
            return True
    return False


def _band_y_offsets(
    sections: Sequence[_CompileSection],
    topology_by_section: Mapping[str, CompiledSectionTopology],
    effective_ranks: Mapping[str, int],
    raw_band_by_section: Mapping[str, int],
    facts: GraphInventoryFacts,
    furniture_by_ref: Mapping[CanonicalNodeRef, NodeFurnitureFact],
    options: _LayoutOptions,
    spacing: _Spacing,
    plan: LayoutPlanV1 | None,
    estimate_section_size: _SectionSizeEstimator,
    *,
    collapse_islands: bool,
) -> dict[tuple[str, int, int], int]:
    lane_heights: dict[tuple[str, int, int, int], int] = {}
    for section in sections:
        topology = _topology_for(section, topology_by_section)
        island_index = 0 if collapse_islands else topology.island_index
        band = raw_band_by_section[section.id]
        rank = effective_ranks[section.id]
        estimated_height = _estimated_section_height(
            section,
            facts,
            furniture_by_ref,
            options,
            spacing,
            plan,
            estimate_section_size,
        )
        lane_key = (topology.scope_path, island_index, band, rank)
        lane_heights[lane_key] = (
            lane_heights.get(lane_key, 0) + estimated_height + spacing.section_gap_y
        )

    bands_by_island: dict[tuple[str, int], dict[int, int]] = {}
    for (scope_path, island_index, band, _rank), lane_height in lane_heights.items():
        band_heights = bands_by_island.setdefault((scope_path, island_index), {})
        band_heights[band] = max(
            band_heights.get(band, 0),
            max(0, lane_height - spacing.section_gap_y),
        )

    offsets: dict[tuple[str, int, int], int] = {}
    for island_key, band_heights in sorted(bands_by_island.items()):
        y = 0
        for band in sorted(band_heights):
            offsets[(*island_key, band)] = y
            y += band_heights[band] + spacing.band_gap_y
    return offsets


def _estimated_section_height(
    section: _CompileSection,
    facts: GraphInventoryFacts,
    furniture_by_ref: Mapping[CanonicalNodeRef, NodeFurnitureFact],
    options: _LayoutOptions,
    spacing: _Spacing,
    plan: LayoutPlanV1 | None,
    estimate_section_size: _SectionSizeEstimator,
) -> int:
    return estimate_section_size(
        section, facts, furniture_by_ref, options, spacing, plan
    )[1]


def _section_semantic_sort_key(section: _CompileSection) -> tuple[Any, ...]:
    node_ranks = tuple(_ref_sort_key(ref) for ref in section.node_refs)
    return (
        _common_scope(section.node_refs),
        _section_title_sort_rank(section.title),
        section.kind,
        section.id,
        node_ranks,
    )


def _section_title_sort_rank(title: str) -> int:
    lowered = title.lower()
    if "model" in lowered:
        return 0
    if "lora" in lowered or "vae" in lowered or "clip" in lowered:
        return 1
    if "input" in lowered:
        return 2
    if "setting" in lowered:
        return 3
    if "conditioning" in lowered:
        return 10
    if "prompt" in lowered:
        return 11
    if "latent" in lowered or "prepare" in lowered:
        return 20
    if "first" in lowered and "sampler" in lowered:
        return 30
    if "sampler" in lowered or "sampling" in lowered:
        return 31
    if "optional" in lowered:
        return 32
    if "decode" in lowered:
        return 40
    if "postprocess" in lowered:
        return 41
    if "output" in lowered or "save" in lowered:
        return 50
    if "set / get" in lowered:
        return 80
    if "label" in lowered or "note" in lowered:
        return 81
    return 60


def _stable_auto_name(section: _CompileSection, scc_id: str) -> str:
    raw = section.title or section.id
    slug = "".join(char.lower() if char.isalnum() else "_" for char in raw).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    if not slug:
        slug = "section"
    digest_payload = "|".join(
        [
            section.id,
            section.kind,
            scc_id,
            *(_entry_key(ref) for ref in section.node_refs),
        ]
    )
    digest = hashlib.blake2b(digest_payload.encode("utf-8"), digest_size=4).hexdigest()
    return f"{slug}_{digest}"


def _common_scope(refs: Sequence[CanonicalNodeRef]) -> str:
    if not refs:
        return ""
    scopes = {ref.scope_path for ref in refs}
    return scopes.pop() if len(scopes) == 1 else ""


def _ref_sort_key(ref: CanonicalNodeRef) -> tuple[int, str, str]:
    return (0 if ref.scope_path == "" else 1, ref.scope_path, ref.uid)


def _id_sort_key(value: str) -> tuple[int, str]:
    return (0, value.zfill(20)) if value.isdigit() else (1, value)


def _entry_key(ref: CanonicalNodeRef) -> str:
    return make_uid(ref.scope_path, ref.uid)
