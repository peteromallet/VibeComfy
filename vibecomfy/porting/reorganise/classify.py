from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .graph_facts import (
    CanonicalRefFact,
    GraphInventoryFacts,
    ScopeTopologyFacts,
    TopologyEdgeFact,
    extract_graph_facts,
)
from .plan_types import (
    HELPER_CLASS_TYPES,
    ROLE_HINT_CONDITIONING,
    ROLE_HINT_CONTROL,
    ROLE_HINT_DECODE,
    ROLE_HINT_HELPER,
    ROLE_HINT_LATENT,
    ROLE_HINT_LOADER,
    ROLE_HINT_OUTPUT,
    ROLE_HINT_POSTPROCESS,
    ROLE_HINT_SAMPLER,
    ROLE_HINT_UI,
    ROLE_HINT_UNKNOWN,
    ROLE_HINT_UTILITY,
    ROLE_HINTS,
    CanonicalNodeRef,
    RoleHint,
)

REASON_CLASS_NAME_CONDITIONING = "class_name_conditioning"
REASON_CLASS_NAME_CONTROL = "class_name_control"
REASON_CLASS_NAME_DECODE = "class_name_decode"
REASON_CLASS_NAME_LATENT = "class_name_latent"
REASON_CLASS_NAME_LOADER = "class_name_loader"
REASON_CLASS_NAME_OUTPUT = "class_name_output"
REASON_CLASS_NAME_POSTPROCESS = "class_name_postprocess"
REASON_CLASS_NAME_SAMPLER = "class_name_sampler"
REASON_CLASS_NAME_UTILITY = "class_name_utility"
REASON_EQUIVALENT_SINGLE_NODE_SIBLING_PAIR = "equivalent_single_node_sibling_pair"
REASON_HELPER_NODE = "helper_node"
REASON_BRANCH_PIPELINE_TERMINAL = "branch_pipeline_terminal"
REASON_SIMPLE_LATENT_SOURCE_TO_SAMPLING = "simple_latent_source_to_sampling"
REASON_UI_NODE = "ui_node"
REASON_UNKNOWN_UNASSIGNED = "unknown_unassigned"
REASON_VAE_DECODE_TO_OUTPUT_FOLD = "vae_decode_to_output_fold"

OUTPUT_CLASS_TYPES: frozenset[str] = frozenset(
    {
        "PreviewAudio",
        "PreviewImage",
        "PreviewString",
        "SaveAnimatedPNG",
        "SaveAnimatedWEBP",
        "SaveAudio",
        "SaveAudioMP3",
        "SaveAudioOpus",
        "SaveGLB",
        "SaveImage",
        "SaveImageAdvanced",
        "SaveImagesResponse",
        "SaveLatent",
        "SaveString",
        "SaveSVGNode",
        "SaveVideo",
        "SaveWEBM",
        "VHS_VideoCombine",
    }
)

UI_HELPER_CLASS_TYPES: frozenset[str] = frozenset({"Note", "MarkdownNote"})


def _freeze_jsonish(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze_jsonish(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze_jsonish(item) for item in value)
    return value


def _thaw_jsonish(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw_jsonish(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_jsonish(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class RoleClassificationHint:
    ref: CanonicalNodeRef
    class_type: str
    role_hint: RoleHint
    confidence: float
    reason_codes: tuple[str, ...]
    related_refs: tuple[CanonicalNodeRef, ...] = ()
    detail: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.role_hint not in ROLE_HINTS:
            raise ValueError(f"unknown role hint: {self.role_hint!r}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0, 1]: {self.confidence!r}")
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        object.__setattr__(self, "related_refs", tuple(self.related_refs))
        object.__setattr__(self, "detail", _freeze_jsonish(self.detail))

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ref": self.ref.to_json(),
            "class_type": self.class_type,
            "role_hint": self.role_hint,
            "confidence": self.confidence,
            "reason_codes": list(self.reason_codes),
            "related_refs": [ref.to_json() for ref in self.related_refs],
        }
        if self.detail:
            payload["detail"] = _thaw_jsonish(self.detail)
        return payload


@dataclass(frozen=True, slots=True)
class ClassificationReport:
    hints: tuple[RoleClassificationHint, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "hints", tuple(self.hints))

    def hint_for(self, ref: CanonicalNodeRef) -> RoleClassificationHint | None:
        for hint in self.hints:
            if hint.ref == ref:
                return hint
        return None

    def to_json(self) -> dict[str, Any]:
        return {"hints": [hint.to_json() for hint in self.hints]}


@dataclass(frozen=True, slots=True)
class _TopologyIndex:
    incoming: Mapping[CanonicalNodeRef, tuple[TopologyEdgeFact, ...]]
    outgoing: Mapping[CanonicalNodeRef, tuple[TopologyEdgeFact, ...]]
    branch_terminal_refs: frozenset[CanonicalNodeRef]
    class_type_by_ref: Mapping[CanonicalNodeRef, str]


def classify_layout_facts(
    facts: GraphInventoryFacts,
    *,
    candidate_refs: Sequence[CanonicalNodeRef] | None = None,
) -> ClassificationReport:
    """Return deterministic role hints for default unassigned classification.

    The hints are deliberately explanatory only: this function never assigns
    coordinates, changes section ownership, or mutates topology.
    """

    canonical_by_ref = {fact.ref: fact for fact in facts.canonical_refs}
    topology_by_scope = {topology.scope_path: topology for topology in facts.scope_topologies}
    topology_index_by_scope = {
        scope_path: _topology_index(topology, canonical_by_ref)
        for scope_path, topology in topology_by_scope.items()
    }
    pair_siblings = _equivalent_single_node_siblings(facts.scope_topologies, canonical_by_ref)
    selected_refs = (
        tuple(candidate_refs)
        if candidate_refs is not None
        else tuple(fact.ref for fact in facts.canonical_refs)
    )

    hints: list[RoleClassificationHint] = []
    for ref in sorted(selected_refs, key=lambda item: item.to_json()):
        fact = canonical_by_ref.get(ref)
        if fact is None:
            continue
        topology_index = topology_index_by_scope.get(
            ref.scope_path,
            _TopologyIndex(
                incoming={},
                outgoing={},
                branch_terminal_refs=frozenset(),
                class_type_by_ref={},
            ),
        )
        hints.append(_classify_node(fact, topology_index, pair_siblings.get(ref, ())))
    return ClassificationReport(hints=tuple(hints))


def classify_layout_from_ui(
    ui_json: Mapping[str, Any],
    *,
    sidecar_envelope: Mapping[str, Any] | None = None,
    candidate_refs: Sequence[CanonicalNodeRef] | None = None,
) -> ClassificationReport:
    return classify_layout_facts(
        extract_graph_facts(ui_json, sidecar_envelope=sidecar_envelope),
        candidate_refs=candidate_refs,
    )


def _classify_node(
    fact: CanonicalRefFact,
    topology: _TopologyIndex,
    sibling_refs: Sequence[CanonicalNodeRef],
) -> RoleClassificationHint:
    if fact.is_helper:
        role = ROLE_HINT_UI if fact.class_type in UI_HELPER_CLASS_TYPES else ROLE_HINT_HELPER
        reason = REASON_UI_NODE if role == ROLE_HINT_UI else REASON_HELPER_NODE
        return RoleClassificationHint(
            ref=fact.ref,
            class_type=fact.class_type,
            role_hint=role,
            confidence=0.99,
            reason_codes=(reason,),
        )

    outgoing = topology.outgoing.get(fact.ref, ())
    branch_terminal = fact.ref in topology.branch_terminal_refs

    if branch_terminal and _is_decode_class(fact.class_type):
        return _hint(
            fact,
            ROLE_HINT_DECODE,
            0.9,
            (REASON_BRANCH_PIPELINE_TERMINAL, REASON_CLASS_NAME_DECODE),
            sibling_refs,
            {"branch_policy": "decode_output_terminals_remain_separate"},
        )
    if branch_terminal and _is_output_class(fact.class_type):
        return _hint(
            fact,
            ROLE_HINT_OUTPUT,
            0.94,
            (REASON_BRANCH_PIPELINE_TERMINAL, REASON_CLASS_NAME_OUTPUT),
            sibling_refs,
            {"branch_policy": "decode_output_terminals_remain_separate"},
        )
    if _is_vae_decode_class(fact.class_type) and _outgoing_only_to_outputs(outgoing, topology):
        return _hint(
            fact,
            ROLE_HINT_OUTPUT,
            0.88,
            (REASON_VAE_DECODE_TO_OUTPUT_FOLD,),
            sibling_refs,
        )
    if _is_simple_latent_source(fact, topology):
        return _hint(
            fact,
            ROLE_HINT_SAMPLER,
            0.84,
            (REASON_SIMPLE_LATENT_SOURCE_TO_SAMPLING,),
            sibling_refs,
        )

    role, confidence, reason = _class_name_role(fact.class_type)
    if sibling_refs:
        confidence = max(confidence, 0.76)
        return _hint(
            fact,
            role,
            confidence,
            (reason, REASON_EQUIVALENT_SINGLE_NODE_SIBLING_PAIR),
            sibling_refs,
            {"pair_size": len(sibling_refs) + 1},
        )
    return _hint(fact, role, confidence, (reason,), ())


def _hint(
    fact: CanonicalRefFact,
    role: RoleHint,
    confidence: float,
    reason_codes: Sequence[str],
    sibling_refs: Sequence[CanonicalNodeRef],
    detail: Mapping[str, Any] | None = None,
) -> RoleClassificationHint:
    return RoleClassificationHint(
        ref=fact.ref,
        class_type=fact.class_type,
        role_hint=role,
        confidence=round(confidence, 4),
        reason_codes=tuple(reason_codes),
        related_refs=tuple(sorted(sibling_refs, key=lambda ref: ref.to_json())),
        detail=detail or {},
    )


def _topology_index(
    topology: ScopeTopologyFacts,
    canonical_by_ref: Mapping[CanonicalNodeRef, CanonicalRefFact],
) -> _TopologyIndex:
    incoming: dict[CanonicalNodeRef, list[TopologyEdgeFact]] = {}
    outgoing: dict[CanonicalNodeRef, list[TopologyEdgeFact]] = {}
    for edge in topology.effective_edges:
        outgoing.setdefault(edge.source, []).append(edge)
        incoming.setdefault(edge.target, []).append(edge)
    branch_refs: set[CanonicalNodeRef] = set()
    for candidate in topology.parallel_branch_candidates:
        for root in candidate.branch_roots:
            branch_refs.add(root)
        for terminal in candidate.terminal_refs:
            branch_refs.add(terminal)
        reachable = _reachable_refs(candidate.branch_roots, outgoing)
        branch_refs.update(reachable)
    return _TopologyIndex(
        incoming={ref: tuple(sorted(edges, key=_edge_sort_key)) for ref, edges in incoming.items()},
        outgoing={ref: tuple(sorted(edges, key=_edge_sort_key)) for ref, edges in outgoing.items()},
        branch_terminal_refs=frozenset(branch_refs),
        class_type_by_ref={
            ref: fact.class_type
            for ref, fact in canonical_by_ref.items()
            if ref.scope_path == topology.scope_path
        },
    )


def _edge_sort_key(edge: TopologyEdgeFact) -> tuple[list[str], list[str], str, str]:
    return (edge.source.to_json(), edge.target.to_json(), edge.source_slot, edge.target_slot)


def _reachable_refs(
    starts: Sequence[CanonicalNodeRef],
    outgoing: Mapping[CanonicalNodeRef, Sequence[TopologyEdgeFact]],
) -> set[CanonicalNodeRef]:
    pending = list(starts)
    seen: set[CanonicalNodeRef] = set()
    while pending:
        ref = pending.pop(0)
        if ref in seen:
            continue
        seen.add(ref)
        pending.extend(edge.target for edge in outgoing.get(ref, ()) if edge.target not in seen)
    return seen


def _equivalent_single_node_siblings(
    topologies: Sequence[ScopeTopologyFacts],
    canonical_by_ref: Mapping[CanonicalNodeRef, CanonicalRefFact],
) -> dict[CanonicalNodeRef, tuple[CanonicalNodeRef, ...]]:
    siblings: dict[CanonicalNodeRef, tuple[CanonicalNodeRef, ...]] = {}
    for topology in topologies:
        index = _topology_index(topology, canonical_by_ref)
        groups: dict[
            tuple[str, str, tuple[tuple[str, str], ...], tuple[tuple[str, str], ...]],
            list[CanonicalNodeRef],
        ] = {}
        for node in topology.node_topology:
            fact = canonical_by_ref.get(node.ref)
            if fact is None or fact.is_helper:
                continue
            incoming_refs = tuple(tuple(edge.source.to_json()) for edge in index.incoming.get(node.ref, ()))
            outgoing_refs = tuple(tuple(edge.target.to_json()) for edge in index.outgoing.get(node.ref, ()))
            if not incoming_refs and not outgoing_refs:
                continue
            key = (node.ref.scope_path, fact.class_type, incoming_refs, outgoing_refs)
            groups.setdefault(key, []).append(node.ref)
        for refs in groups.values():
            if len(refs) != 2:
                continue
            ordered = tuple(sorted(refs, key=lambda ref: ref.to_json()))
            for ref in ordered:
                siblings[ref] = tuple(item for item in ordered if item != ref)
    return siblings


def _outgoing_only_to_outputs(edges: Sequence[TopologyEdgeFact], topology: _TopologyIndex) -> bool:
    return bool(edges) and all(
        _is_output_class(topology.class_type_by_ref.get(edge.target, ""))
        or _edge_targets_output(edge)
        for edge in edges
    )


def _edge_targets_output(edge: TopologyEdgeFact) -> bool:
    target_uid = edge.target.uid.lower()
    return any(token in target_uid for token in ("save", "preview", "combine", "output"))


def _is_simple_latent_source(fact: CanonicalRefFact, topology: _TopologyIndex) -> bool:
    lower = fact.class_type.lower()
    if "latent" not in lower:
        return False
    if topology.incoming.get(fact.ref):
        return False
    outgoing = topology.outgoing.get(fact.ref, ())
    if len(outgoing) != 1:
        return False
    target_classish = topology.class_type_by_ref.get(outgoing[0].target, outgoing[0].target.uid).lower()
    return "sample" in target_classish or "sampler" in target_classish


def _class_name_role(class_type: str) -> tuple[RoleHint, float, str]:
    lower = class_type.lower()
    if _is_output_class(class_type):
        return ROLE_HINT_OUTPUT, 0.92, REASON_CLASS_NAME_OUTPUT
    if _is_sampler_class(class_type):
        return ROLE_HINT_SAMPLER, 0.92, REASON_CLASS_NAME_SAMPLER
    if _is_decode_class(class_type):
        return ROLE_HINT_DECODE, 0.82, REASON_CLASS_NAME_DECODE
    if "conditioning" in lower or "cliptextencode" in lower or "guider" in lower:
        return ROLE_HINT_CONDITIONING, 0.86, REASON_CLASS_NAME_CONDITIONING
    if "controlnet" in lower or "control" in lower:
        return ROLE_HINT_CONTROL, 0.82, REASON_CLASS_NAME_CONTROL
    if "latent" in lower:
        return ROLE_HINT_LATENT, 0.72, REASON_CLASS_NAME_LATENT
    if "upscale" in lower or "resize" in lower or "crop" in lower:
        return ROLE_HINT_POSTPROCESS, 0.72, REASON_CLASS_NAME_POSTPROCESS
    if "loader" in lower or lower.startswith(("checkpoint", "clip", "unet", "vae")):
        return ROLE_HINT_LOADER, 0.84, REASON_CLASS_NAME_LOADER
    if lower.startswith(("primitive", "random", "string", "int", "float", "boolean")):
        return ROLE_HINT_UTILITY, 0.68, REASON_CLASS_NAME_UTILITY
    return ROLE_HINT_UNKNOWN, 0.2, REASON_UNKNOWN_UNASSIGNED


def _is_output_class(class_type: str) -> bool:
    lower = class_type.lower()
    return (
        class_type in OUTPUT_CLASS_TYPES
        or "save" in lower
        or lower.startswith("preview")
        or "videocombine" in lower
        or lower.endswith("combine")
    )


def _is_sampler_class(class_type: str) -> bool:
    return "sampler" in class_type.lower()


def _is_decode_class(class_type: str) -> bool:
    lower = class_type.lower()
    return "decode" in lower or "decoder" in lower


def _is_vae_decode_class(class_type: str) -> bool:
    lower = class_type.lower()
    return "vae" in lower and "decode" in lower


__all__ = [
    "ClassificationReport",
    "OUTPUT_CLASS_TYPES",
    "REASON_BRANCH_PIPELINE_TERMINAL",
    "REASON_CLASS_NAME_CONDITIONING",
    "REASON_CLASS_NAME_CONTROL",
    "REASON_CLASS_NAME_DECODE",
    "REASON_CLASS_NAME_LATENT",
    "REASON_CLASS_NAME_LOADER",
    "REASON_CLASS_NAME_OUTPUT",
    "REASON_CLASS_NAME_POSTPROCESS",
    "REASON_CLASS_NAME_SAMPLER",
    "REASON_CLASS_NAME_UTILITY",
    "REASON_EQUIVALENT_SINGLE_NODE_SIBLING_PAIR",
    "REASON_HELPER_NODE",
    "REASON_SIMPLE_LATENT_SOURCE_TO_SAMPLING",
    "REASON_UI_NODE",
    "REASON_UNKNOWN_UNASSIGNED",
    "REASON_VAE_DECODE_TO_OUTPUT_FOLD",
    "RoleClassificationHint",
    "UI_HELPER_CLASS_TYPES",
    "classify_layout_facts",
    "classify_layout_from_ui",
]
