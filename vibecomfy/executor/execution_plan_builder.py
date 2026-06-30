"""Deterministic routing helpers for precedent-backed execution plans."""

from __future__ import annotations

import re
import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from vibecomfy.comfy_nodes.agent.execution_plan import (
    ExecutionPlan,
    PlanCondition,
    PlanStep,
    RoleBinding,
    SocketRef,
)
from vibecomfy.comfy_nodes.agent.session import structural_graph_hash
from vibecomfy.executor.graph_inspection import inspect_graph

_NON_PLANNING_ROUTES = frozenset({"revise", "respond", "inspect", "research", "clarify"})

_PLANNING_SIGNAL_RE = re.compile(
    r"\b("
    r"precedents?|templates?|workflow(?:s)?|community\s+examples?|"
    r"custom(?:[-_\s]+nodes?)?|external(?:[-_\s]+workflow)?|"
    r"examples?|reference(?:[-_\s]+workflow)?"
    r")\b",
    re.IGNORECASE,
)

_NAMED_TECHNOLOGY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("HotShotXL", re.compile(r"\bhot\s*shot\s*xl\b|\bhotshotxl\b", re.IGNORECASE)),
    ("Wan", re.compile(r"\bwan(?:video)?(?:\s*[-_.]?\s*\d+(?:\.\d+)*)?\b", re.IGNORECASE)),
    ("LTX", re.compile(r"\bltx(?:video)?(?:\s*[-_.]?\s*\d+(?:\.\d+)*)?\b", re.IGNORECASE)),
    ("AnimateDiff", re.compile(r"\banimate\s*diff\b|\banimatediff\b", re.IGNORECASE)),
    ("IPAdapter", re.compile(r"\bip\s*[-_]?\s*adapter\b|\bipadapter\b", re.IGNORECASE)),
    ("ControlNet", re.compile(r"\bcontrol\s*net\b|\bcontrolnet\b", re.IGNORECASE)),
)

_CLASSIFY_TEXT_FIELDS = (
    "plan_summary",
    "research_goal",
    "known_graph_context",
    "pattern_category",
    "change_goal",
    "task",
)

_CLASSIFY_SEQUENCE_FIELDS = (
    "search_directions",
    "source_preferences",
    "model_families",
    "avoid",
)

_GRAPH_FACT_FIELDS = (
    "current_output_node_types",
    "terminal_output_socket_types",
    "socket_type_mismatches",
    "missing_required_inputs",
    "unknown_class_types",
    "missing_models",
    "missing_node_packs",
    "readiness_blockers",
    "summary",
)

_HOTSHOTXL_ROLE_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "role": "base_model",
        "class_types": ("CheckpointLoaderSimple",),
        "required": False,
        "inputs": {},
        "outputs": {"model": "MODEL", "clip": "CLIP", "vae": "VAE"},
        "widgets": {"ckpt_name": "widget_0"},
    },
    {
        "role": "hotshotxl_motion_model",
        "class_types": ("HotshotXLLoader",),
        "required": True,
        "inputs": {},
        "outputs": {"motion_model": "MOTION_MODEL"},
        "widgets": {"model_name": "widget_0"},
    },
    {
        "role": "animatediff_context",
        "class_types": ("ADE_AnimateDiffLoaderWithContext",),
        "required": True,
        "inputs": {"model": "MODEL", "motion_model": "MOTION_MODEL"},
        "outputs": {"model": "MODEL"},
        "widgets": {},
    },
    {
        "role": "latent_source",
        "class_types": ("EmptyLatentImage",),
        "required": True,
        "inputs": {},
        "outputs": {"latent": "LATENT"},
        "widgets": {
            "width": "widget_0",
            "height": "widget_1",
            "batch_size": "widget_2",
        },
    },
    {
        "role": "sampler",
        "class_types": ("KSampler", "KSamplerAdvanced"),
        "required": True,
        "inputs": {
            "model": "MODEL",
            "positive": "CONDITIONING",
            "negative": "CONDITIONING",
            "latent_image": "LATENT",
        },
        "outputs": {"samples": "LATENT"},
        "widgets": {
            "seed": "widget_0",
            "steps": "widget_1",
            "cfg": "widget_2",
            "sampler_name": "widget_3",
            "scheduler": "widget_4",
            "denoise": "widget_5",
        },
    },
    {
        "role": "decoder",
        "class_types": ("VAEDecode",),
        "required": True,
        "inputs": {"samples": "LATENT", "vae": "VAE"},
        "outputs": {"images": "IMAGE"},
        "widgets": {},
    },
    {
        "role": "video_terminal",
        "class_types": ("VHS_VideoCombine",),
        "required": True,
        "inputs": {"images": "IMAGE"},
        "outputs": {},
        "widgets": {"frame_rate": "widget_1", "filename_prefix": "widget_2"},
    },
)

_HOTSHOTXL_PATTERN_EDGES: tuple[tuple[str, str, str, str, bool], ...] = (
    ("base_model", "animatediff_context", "model", "model", False),
    ("hotshotxl_motion_model", "animatediff_context", "motion_model", "motion_model", True),
    ("animatediff_context", "sampler", "model", "model", True),
    ("latent_source", "sampler", "latent", "latent_image", True),
    ("sampler", "decoder", "samples", "samples", True),
    ("decoder", "video_terminal", "images", "images", True),
)

_CLASS_TO_ROLE: dict[str, dict[str, Any]] = {
    class_type: role_definition
    for role_definition in _HOTSHOTXL_ROLE_DEFINITIONS
    for class_type in role_definition["class_types"]
}

_VIDEO_TERMINAL_CLASSES = frozenset({"VHS_VideoCombine"})


def _freeze_jsonish(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({
            str(key): _freeze_jsonish(value[key])
            for key in sorted(value, key=lambda item: str(item))
        })
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_jsonish(item) for item in value)
    return value


def _thaw_jsonish(value: Any) -> Any:
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return value.to_dict()
    if isinstance(value, Mapping):
        return {
            str(key): _thaw_jsonish(value[key])
            for key in sorted(value, key=lambda item: str(item))
        }
    if isinstance(value, tuple):
        return [_thaw_jsonish(item) for item in value]
    if isinstance(value, list):
        return [_thaw_jsonish(item) for item in value]
    return value


def _stable_json_hash(value: Any, *, length: int = 12) -> str:
    payload = json.dumps(_thaw_jsonish(value), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:length]


@dataclass(frozen=True)
class NormalizedRoleEvidence:
    role: str
    class_types: tuple[str, ...] = ()
    required: bool = True
    input_sockets: Mapping[str, str] = field(default_factory=dict)
    output_sockets: Mapping[str, str] = field(default_factory=dict)
    widgets: Mapping[str, Any] = field(default_factory=dict)
    models: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    unresolved: tuple[Mapping[str, Any], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "class_types", tuple(self.class_types))
        object.__setattr__(self, "input_sockets", _freeze_jsonish(self.input_sockets))
        object.__setattr__(self, "output_sockets", _freeze_jsonish(self.output_sockets))
        object.__setattr__(self, "widgets", _freeze_jsonish(self.widgets))
        object.__setattr__(self, "models", tuple(self.models))
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))
        object.__setattr__(
            self,
            "unresolved",
            tuple(_freeze_jsonish(item) for item in self.unresolved),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "class_types": list(self.class_types),
            "required": self.required,
            "input_sockets": _thaw_jsonish(self.input_sockets),
            "output_sockets": _thaw_jsonish(self.output_sockets),
            "widgets": _thaw_jsonish(self.widgets),
            "models": list(self.models),
            "evidence_refs": list(self.evidence_refs),
            "unresolved": _thaw_jsonish(self.unresolved),
        }


@dataclass(frozen=True)
class NormalizedPatternEdge:
    source_role: str
    target_role: str
    source_socket: str
    target_socket: str
    required: bool = True
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_role": self.source_role,
            "target_role": self.target_role,
            "source_socket": self.source_socket,
            "target_socket": self.target_socket,
            "required": self.required,
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass(frozen=True)
class NormalizedPrecedentEvidence:
    technologies: tuple[str, ...] = ()
    media_domains: tuple[str, ...] = ()
    roles: tuple[NormalizedRoleEvidence, ...] = ()
    required_classes: tuple[str, ...] = ()
    terminal_role: str | None = None
    pattern_edges: tuple[NormalizedPatternEdge, ...] = ()
    model_evidence: tuple[Mapping[str, Any], ...] = ()
    widget_evidence: Mapping[str, Any] = field(default_factory=dict)
    schema_provenance: Mapping[str, Any] = field(default_factory=dict)
    runtime_provenance: Mapping[str, Any] = field(default_factory=dict)
    unresolved_evidence: tuple[Mapping[str, Any], ...] = ()
    source_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "technologies", tuple(self.technologies))
        object.__setattr__(self, "media_domains", tuple(self.media_domains))
        object.__setattr__(self, "roles", tuple(self.roles))
        object.__setattr__(self, "required_classes", tuple(self.required_classes))
        object.__setattr__(self, "pattern_edges", tuple(self.pattern_edges))
        object.__setattr__(
            self,
            "model_evidence",
            tuple(_freeze_jsonish(item) for item in self.model_evidence),
        )
        object.__setattr__(self, "widget_evidence", _freeze_jsonish(self.widget_evidence))
        object.__setattr__(self, "schema_provenance", _freeze_jsonish(self.schema_provenance))
        object.__setattr__(self, "runtime_provenance", _freeze_jsonish(self.runtime_provenance))
        object.__setattr__(
            self,
            "unresolved_evidence",
            tuple(_freeze_jsonish(item) for item in self.unresolved_evidence),
        )
        object.__setattr__(self, "source_refs", tuple(self.source_refs))

    def to_dict(self) -> dict[str, Any]:
        return {
            "technologies": list(self.technologies),
            "media_domains": list(self.media_domains),
            "roles": [role.to_dict() for role in self.roles],
            "required_classes": list(self.required_classes),
            "terminal_role": self.terminal_role,
            "pattern_edges": [edge.to_dict() for edge in self.pattern_edges],
            "model_evidence": _thaw_jsonish(self.model_evidence),
            "widget_evidence": _thaw_jsonish(self.widget_evidence),
            "schema_provenance": _thaw_jsonish(self.schema_provenance),
            "runtime_provenance": _thaw_jsonish(self.runtime_provenance),
            "unresolved_evidence": _thaw_jsonish(self.unresolved_evidence),
            "source_refs": list(self.source_refs),
        }


def _effective_route(classify_result: Any) -> str:
    route = getattr(classify_result, "effective_route", "")
    if callable(route):
        route = route()
    if route:
        return str(route).strip()
    route = getattr(classify_result, "route", "")
    if route:
        return str(route).strip()
    return ""


def _effective_task(classify_result: Any) -> str:
    task = getattr(classify_result, "effective_task", "")
    if callable(task):
        task = task()
    if task:
        return str(task).strip()
    task = getattr(classify_result, "task", "")
    if task:
        return str(task).strip()
    return ""


def _iter_text(value: Any) -> Iterable[str]:
    if value is None:
        return
    if isinstance(value, str):
        if value.strip():
            yield value
        return
    if isinstance(value, Mapping):
        for key in sorted(value, key=lambda item: str(item)):
            yield from _iter_text(key)
            yield from _iter_text(value[key])
        return
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
        for item in value:
            yield from _iter_text(item)
        return
    text = str(value).strip()
    if text:
        yield text


def _field_value(source: Any, field: str) -> Any:
    if source is None:
        return None
    if isinstance(source, Mapping):
        return source.get(field)
    return getattr(source, field, None)


def _iter_classify_signal_text(classify_result: Any) -> Iterable[str]:
    for field in _CLASSIFY_TEXT_FIELDS:
        yield from _iter_text(_field_value(classify_result, field))
    for field in _CLASSIFY_SEQUENCE_FIELDS:
        yield from _iter_text(_field_value(classify_result, field))
    effective_task = _effective_task(classify_result)
    if effective_task:
        yield effective_task


def _iter_graph_fact_text(graph_facts: Any) -> Iterable[str]:
    if graph_facts is None:
        return
    if hasattr(graph_facts, "to_dict") and callable(graph_facts.to_dict):
        graph_facts = graph_facts.to_dict()
    if isinstance(graph_facts, Mapping):
        for field in _GRAPH_FACT_FIELDS:
            yield from _iter_text(graph_facts.get(field))
        return
    for field in _GRAPH_FACT_FIELDS:
        yield from _iter_text(getattr(graph_facts, field, None))


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "to_dict") and callable(value.to_dict):
        value = value.to_dict()
    return value if isinstance(value, Mapping) else {}


def _as_sequence(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Mapping):
        return (value,)
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
        return tuple(value)
    return (value,)


def _unique_stable_strings(values: Any) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for text in _iter_text(values):
        item = str(text).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return tuple(result)


def _mapping_sequence_field(source: Any, field: str) -> tuple[Mapping[str, Any], ...]:
    source_mapping = _as_mapping(source)
    values = _as_sequence(source_mapping.get(field))
    return tuple(item for item in (_as_mapping(value) for value in values) if item)


def _source_semantics(source: Mapping[str, Any]) -> Mapping[str, Any]:
    semantics = source.get("workflow_semantics")
    return semantics if isinstance(semantics, Mapping) else {}


def _workflow_schema(source: Mapping[str, Any]) -> Mapping[str, Any]:
    schema = source.get("workflow_schema")
    return schema if isinstance(schema, Mapping) else {}


def _schema_class_entry(source: Mapping[str, Any], class_type: str) -> Mapping[str, Any]:
    entry = _workflow_schema(source).get(class_type)
    return entry if isinstance(entry, Mapping) else {}


def _schema_socket_map(
    class_schema: Mapping[str, Any],
    direction: str,
) -> dict[str, str]:
    if not class_schema:
        return {}
    if direction == "inputs":
        raw_input = class_schema.get("input")
        input_schema = raw_input if isinstance(raw_input, Mapping) else {}
        result: dict[str, str] = {}
        for group in ("required", "optional"):
            group_schema = input_schema.get(group)
            if not isinstance(group_schema, Mapping):
                continue
            for name, spec in group_schema.items():
                if isinstance(spec, Mapping):
                    socket_type = spec.get("type") or spec.get("socket_type")
                elif isinstance(spec, (list, tuple)) and spec:
                    socket_type = spec[0]
                else:
                    socket_type = spec
                if socket_type is not None:
                    result[str(name)] = str(socket_type)
        return result

    outputs = class_schema.get("outputs")
    result = {}
    for index, output in enumerate(_as_sequence(outputs)):
        if isinstance(output, Mapping):
            name = output.get("name") or output.get("socket") or f"output_{index}"
            socket_type = output.get("type") or output.get("socket_type") or name
        elif isinstance(output, (list, tuple)) and len(output) >= 2:
            name = output[0]
            socket_type = output[1]
        else:
            name = f"output_{index}"
            socket_type = output
        if socket_type is not None:
            result[str(name)] = str(socket_type)
    return result


def _collect_class_evidence(
    research_result: Any,
    classify_result: Any,
    task: Any,
) -> tuple[dict[str, list[str]], tuple[Mapping[str, Any], ...], Mapping[str, Any], Mapping[str, Any]]:
    research_mapping = _as_mapping(research_result)
    selected = _as_mapping(research_mapping.get("selected_precedent"))
    packet = _as_mapping(research_mapping.get("precedent_packet"))
    sources = _mapping_sequence_field(research_mapping, "precedent_sources")

    class_refs: dict[str, list[str]] = {}

    def add_class(class_type: Any, evidence_ref: str) -> None:
        text = str(class_type or "").strip()
        if not text:
            return
        class_refs.setdefault(text, [])
        if evidence_ref not in class_refs[text]:
            class_refs[text].append(evidence_ref)

    for field in ("minimal_spine", "terminal_output_path"):
        for class_type in _as_sequence(selected.get(field)):
            add_class(class_type, f"selected_precedent.{field}")

    for source_index, source in enumerate(sources):
        for class_type in _as_sequence(source.get("node_types")):
            add_class(class_type, f"precedent_sources[{source_index}].node_types")
        semantics = _source_semantics(source)
        for class_type in _as_sequence(semantics.get("node_types")):
            add_class(class_type, f"precedent_sources[{source_index}].workflow_semantics.node_types")
        for class_type in _workflow_schema(source):
            add_class(class_type, f"precedent_sources[{source_index}].workflow_schema")

    for option_index, option in enumerate(_as_sequence(packet.get("options"))):
        option_mapping = _as_mapping(option)
        add_class(option_mapping.get("source_class_type"), f"precedent_packet.options[{option_index}].source_class_type")
        for class_type in _as_sequence(option_mapping.get("node_types")):
            add_class(class_type, f"precedent_packet.options[{option_index}].node_types")

    for field in _CLASSIFY_SEQUENCE_FIELDS:
        for class_type in _as_sequence(_field_value(classify_result, field)):
            if str(class_type).strip() in _CLASS_TO_ROLE:
                add_class(class_type, f"classify_result.{field}")
    for class_type in detect_named_external_technologies(task, tuple(_iter_classify_signal_text(classify_result))):
        if class_type == "HotShotXL":
            add_class("HotshotXLLoader", "named_technology.HotShotXL")

    return class_refs, sources, selected, packet


def _source_refs_for_research(
    sources: tuple[Mapping[str, Any], ...],
    selected: Mapping[str, Any],
) -> tuple[str, ...]:
    refs: list[str] = []
    selected_name = str(selected.get("name") or "").strip()
    if selected_name:
        refs.append(f"selected_precedent:{selected_name}")
    for source_index, source in enumerate(sources):
        source_ref = (
            source.get("source_workflow_path")
            or source.get("path")
            or source.get("url")
            or source.get("class_type")
            or f"precedent_sources[{source_index}]"
        )
        refs.append(str(source_ref))
    return tuple(_unique_stable_strings(refs))


def _models_from_research(
    sources: tuple[Mapping[str, Any], ...],
    selected: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    evidence: list[dict[str, Any]] = []
    for model in _unique_stable_strings(selected.get("models")):
        evidence.append({"model": model, "source": "selected_precedent.models"})
    for source_index, source in enumerate(sources):
        semantics = _source_semantics(source)
        for model in _unique_stable_strings((source.get("models"), semantics.get("models"))):
            item = {
                "model": model,
                "source": f"precedent_sources[{source_index}]",
            }
            if item not in evidence:
                evidence.append(item)
    return tuple(evidence)


def _models_for_role(role: str, model_evidence: tuple[Mapping[str, Any], ...]) -> tuple[str, ...]:
    role_markers = {
        "hotshotxl_motion_model": ("hotshot", "motion"),
        "animatediff_context": ("animatediff", "motion"),
        "base_model": ("sdxl", "checkpoint", "base", "safetensors"),
    }.get(role, ())
    if not role_markers:
        return ()
    matched: list[str] = []
    for item in model_evidence:
        model = str(item.get("model") or "").strip()
        if not model:
            continue
        lowered = model.casefold()
        if any(marker in lowered for marker in role_markers):
            matched.append(model)
    return _unique_stable_strings(matched)


def _frame_count_from_task(task: Any, classify_result: Any, selected: Mapping[str, Any]) -> int | None:
    text_values = (
        task,
        tuple(_iter_classify_signal_text(classify_result)),
        selected.get("requested_terms"),
        selected.get("match_reasons"),
    )
    for text in _iter_text(text_values):
        match = re.search(r"\b(?P<count>\d{1,4})\s*(?:frames?|frame\b)", text, re.IGNORECASE)
        if match:
            return int(match.group("count"))
    gates = selected.get("promotion_gates")
    if isinstance(gates, Mapping):
        for key in ("frame_count", "frames", "batch_size"):
            value = gates.get(key)
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.isdigit():
                return int(value)
    return None


def _media_domains(
    task: Any,
    classify_result: Any,
    selected: Mapping[str, Any],
    class_refs: Mapping[str, list[str]],
) -> tuple[str, ...]:
    text = " ".join(_iter_text((task, tuple(_iter_classify_signal_text(classify_result)), selected)))
    domains: list[str] = []
    if re.search(r"\b(?:video|frames?|fps|motion)\b", text, re.IGNORECASE):
        domains.append("video")
    if any(class_type in _VIDEO_TERMINAL_CLASSES for class_type in class_refs):
        domains.append("video")
    return tuple(_unique_stable_strings(domains))


def _runtime_provenance_for_classes(
    graph_facts: Any,
    required_classes: tuple[str, ...],
) -> dict[str, str]:
    graph_mapping = _as_mapping(graph_facts)
    unknown = set(_unique_stable_strings(graph_mapping.get("unknown_class_types")))
    current_outputs = set(_unique_stable_strings(graph_mapping.get("current_output_node_types")))
    provenance: dict[str, str] = {}
    for class_type in required_classes:
        if class_type in unknown:
            provenance[class_type] = "graph_facts.unknown_class_types"
        elif class_type in current_outputs:
            provenance[class_type] = "graph_facts.current_output_node_types"
        elif graph_mapping:
            provenance[class_type] = "graph_facts.not_reported"
        else:
            provenance[class_type] = "not_checked"
    return provenance


def _schema_provenance_for_role(
    class_type: str,
    sources: tuple[Mapping[str, Any], ...],
) -> tuple[str, Mapping[str, Any]]:
    for source_index, source in enumerate(sources):
        class_schema = _schema_class_entry(source, class_type)
        if class_schema:
            return f"precedent_sources[{source_index}].workflow_schema", class_schema
    return "not_available", {}


def _normalize_precedent_evidence(
    research_result: Any = None,
    *,
    classify_result: Any = None,
    task: Any = None,
    graph_facts: Any = None,
) -> NormalizedPrecedentEvidence | None:
    """Normalize narrow HotShotXL/video precedent evidence for plan building.

    The normalizer is deliberately schema-tolerant. It derives a deterministic
    role/edge skeleton from selected precedent fields, source metadata, packet
    options, classifier context, and the user task. Missing local schema or
    runtime facts are serialized as provenance/unresolved evidence instead of
    aborting normalization.
    """

    class_refs, sources, selected, _packet = _collect_class_evidence(
        research_result,
        classify_result,
        task,
    )
    technologies = detect_named_external_technologies(
        task,
        tuple(_iter_classify_signal_text(classify_result)),
        selected,
        sources,
    )
    known_class_refs = {
        class_type: refs
        for class_type, refs in class_refs.items()
        if class_type in _CLASS_TO_ROLE
    }
    hotshot_requested = "HotShotXL" in technologies or any(
        "hotshot" in class_type.casefold() for class_type in class_refs
    )
    hotshot_pattern = hotshot_requested or any(
        _CLASS_TO_ROLE[class_type]["role"] in {"hotshotxl_motion_model", "animatediff_context"}
        for class_type in known_class_refs
    )
    media_domains = _media_domains(task, classify_result, selected, class_refs)
    video_requested = "video" in media_domains
    if not hotshot_pattern:
        return None

    if hotshot_requested and "HotshotXLLoader" not in known_class_refs:
        known_class_refs["HotshotXLLoader"] = ["unresolved.named_technology.HotShotXL"]

    required_roles = {
        definition["role"]
        for definition in _HOTSHOTXL_ROLE_DEFINITIONS
        if definition["required"]
    }
    present_roles = {
        _CLASS_TO_ROLE[class_type]["role"]
        for class_type in known_class_refs
        if class_type in _CLASS_TO_ROLE
    }
    if hotshot_requested and (video_requested or _VIDEO_TERMINAL_CLASSES.intersection(class_refs)):
        present_roles.update(required_roles)

    model_evidence = _models_from_research(sources, selected)
    frame_count = _frame_count_from_task(task, classify_result, selected)
    role_by_name: dict[str, NormalizedRoleEvidence] = {}
    schema_provenance: dict[str, Any] = {}
    unresolved: list[dict[str, Any]] = []
    widget_evidence: dict[str, Any] = {}

    for definition in _HOTSHOTXL_ROLE_DEFINITIONS:
        role = str(definition["role"])
        matching_classes = tuple(
            class_type
            for class_type in definition["class_types"]
            if class_type in known_class_refs
        )
        if not matching_classes and role not in present_roles:
            continue
        class_types = matching_classes or tuple(definition["class_types"][:1])
        class_type = class_types[0]
        schema_ref, class_schema = _schema_provenance_for_role(class_type, sources)
        schema_provenance[class_type] = schema_ref

        role_unresolved: list[dict[str, Any]] = []
        if schema_ref == "not_available":
            role_unresolved.append({
                "kind": "schema_unavailable",
                "role": role,
                "class_type": class_type,
            })
        if not matching_classes:
            role_unresolved.append({
                "kind": "role_class_missing",
                "role": role,
                "expected_class_types": list(definition["class_types"]),
            })

        input_sockets = _schema_socket_map(class_schema, "inputs") or dict(definition["inputs"])
        output_sockets = _schema_socket_map(class_schema, "outputs") or dict(definition["outputs"])
        widgets = dict(definition["widgets"])
        if role == "latent_source" and frame_count is not None:
            widgets["batch_size_value"] = frame_count
            widget_evidence["latent_source.batch_size"] = {
                "value": frame_count,
                "source": "task",
                "required": True,
            }

        evidence_refs = []
        for known_class in class_types:
            evidence_refs.extend(known_class_refs.get(known_class, ()))
        if not evidence_refs and matching_classes:
            evidence_refs.append(f"class:{class_type}")

        role_evidence = NormalizedRoleEvidence(
            role=role,
            class_types=class_types,
            required=bool(definition["required"]),
            input_sockets=input_sockets,
            output_sockets=output_sockets,
            widgets=widgets,
            models=_models_for_role(role, model_evidence),
            evidence_refs=tuple(_unique_stable_strings(evidence_refs)),
            unresolved=tuple(role_unresolved),
        )
        role_by_name[role] = role_evidence
        unresolved.extend(role_unresolved)

    pattern_edges = tuple(
        NormalizedPatternEdge(
            source_role=source_role,
            target_role=target_role,
            source_socket=source_socket,
            target_socket=target_socket,
            required=required,
            evidence_refs=(
                f"role:{source_role}",
                f"role:{target_role}",
            ),
        )
        for source_role, target_role, source_socket, target_socket, required in _HOTSHOTXL_PATTERN_EDGES
        if source_role in role_by_name and target_role in role_by_name
    )

    ordered_roles = tuple(
        role_by_name[definition["role"]]
        for definition in _HOTSHOTXL_ROLE_DEFINITIONS
        if definition["role"] in role_by_name
    )
    required_classes = tuple(
        role.class_types[0]
        for role in ordered_roles
        if role.required and role.class_types
    )
    terminal_role = "video_terminal" if "video_terminal" in role_by_name else None
    runtime_provenance = _runtime_provenance_for_classes(graph_facts, required_classes)

    return NormalizedPrecedentEvidence(
        technologies=technologies,
        media_domains=media_domains,
        roles=ordered_roles,
        required_classes=required_classes,
        terminal_role=terminal_role,
        pattern_edges=pattern_edges,
        model_evidence=model_evidence,
        widget_evidence=widget_evidence,
        schema_provenance=schema_provenance,
        runtime_provenance=runtime_provenance,
        unresolved_evidence=tuple(unresolved),
        source_refs=_source_refs_for_research(sources, selected),
    )


def _role_by_name(normalized: NormalizedPrecedentEvidence) -> dict[str, NormalizedRoleEvidence]:
    return {role.role: role for role in normalized.roles}


def _role_class(
    roles: Mapping[str, NormalizedRoleEvidence],
    role: str,
    fallback: str,
) -> str:
    evidence = roles.get(role)
    if evidence is not None and evidence.class_types:
        return evidence.class_types[0]
    return fallback


def _role_socket(
    role: str,
    class_type: str,
    *,
    input_name: str | None = None,
    output_name: str | None = None,
) -> SocketRef:
    return SocketRef(
        role=role,
        class_type=class_type,
        input_name=input_name,
        output_name=output_name,
    )


def _selected_precedent_payload(research_result: Any, normalized: NormalizedPrecedentEvidence) -> dict[str, Any]:
    research_mapping = _as_mapping(research_result)
    selected = _as_mapping(research_mapping.get("selected_precedent"))
    if selected:
        return _thaw_jsonish(selected)
    return {
        "media_domains": list(normalized.media_domains),
        "source_refs": list(normalized.source_refs),
        "technologies": list(normalized.technologies),
    }


def _selected_precedent_id(selected_precedent: Mapping[str, Any], normalized: NormalizedPrecedentEvidence) -> str:
    stable_key = (
        selected_precedent.get("source_workflow_path")
        or selected_precedent.get("name")
        or next(iter(normalized.source_refs), "")
        or "hotshotxl-8f"
    )
    return f"precedent.{_stable_json_hash(stable_key)}"


def _plan_provenance(normalized: NormalizedPrecedentEvidence) -> dict[str, Any]:
    return {
        "builder": "vibecomfy.executor.execution_plan_builder.build_execution_plan",
        "normalizer": "hotshotxl_video_v1",
        "source_refs": list(normalized.source_refs),
        "technologies": list(normalized.technologies),
    }


def _role_binding(role: NormalizedRoleEvidence) -> RoleBinding:
    class_type = role.class_types[0] if role.class_types else None
    confidence = "planned" if class_type is not None else "blocked"
    return RoleBinding(
        role=role.role,
        node_ref=SocketRef(role=role.role, class_type=class_type),
        class_type=class_type,
        confidence=confidence,
        evidence={
            "class_types": list(role.class_types),
            "evidence_refs": list(role.evidence_refs),
            "models": list(role.models),
            "required": role.required,
            "unresolved": _thaw_jsonish(role.unresolved),
        },
    )


def _node_id_sort_key(node_id: Any) -> tuple[str, str]:
    text = str(node_id)
    return (text.zfill(12) if text.isdigit() else text, text)


def _candidate_payload(node: Any) -> dict[str, Any]:
    return _thaw_jsonish({
        "node_id": str(node.node_id),
        "class_type": node.class_type,
        "title": node.title,
    })


def _current_graph_role_binding(
    role: NormalizedRoleEvidence,
    graph: Mapping[str, Any],
) -> RoleBinding:
    class_types = tuple(role.class_types)
    class_type = class_types[0] if class_types else None
    evidence = inspect_graph(dict(graph))
    candidates = tuple(
        sorted(
            (
                node
                for node in evidence.nodes
                if not class_types or node.class_type in class_types
            ),
            key=lambda node: _node_id_sort_key(node.node_id),
        )
    )
    base_evidence = {
        "binding_source": "current_graph",
        "candidate_count": len(candidates),
        "class_types": list(class_types),
        "evidence_refs": list(role.evidence_refs),
        "models": list(role.models),
        "required": role.required,
        "unresolved": _thaw_jsonish(role.unresolved),
    }
    if len(candidates) == 1:
        candidate = candidates[0]
        return RoleBinding(
            role=role.role,
            node_ref=SocketRef(
                node_id=str(candidate.node_id),
                role=role.role,
                class_type=candidate.class_type,
            ),
            class_type=candidate.class_type,
            confidence="high",
            evidence={**base_evidence, "candidate": _candidate_payload(candidate)},
        )
    if len(candidates) > 1:
        return RoleBinding(
            role=role.role,
            node_ref=SocketRef(role=role.role, class_type=class_type),
            class_type=class_type,
            confidence="low",
            evidence={
                **base_evidence,
                "ambiguity": "multiple current graph nodes match the required role class types",
                "candidates": [_candidate_payload(candidate) for candidate in candidates],
            },
        )
    return RoleBinding(
        role=role.role,
        node_ref=SocketRef(role=role.role, class_type=class_type),
        class_type=class_type,
        confidence="blocked",
        evidence={
            **base_evidence,
            "ambiguity": "no current graph node matches the required role class types",
        },
    )


def _role_bindings(
    normalized: NormalizedPrecedentEvidence,
    graph: Mapping[str, Any] | None,
) -> tuple[RoleBinding, ...]:
    required_roles = tuple(role for role in normalized.roles if role.required)
    if graph is None:
        return tuple(_role_binding(role) for role in required_roles)
    return tuple(_current_graph_role_binding(role, graph) for role in required_roles)


def _hotshotxl_conditions(
    normalized: NormalizedPrecedentEvidence,
) -> tuple[
    tuple[PlanCondition, ...],
    tuple[PlanCondition, ...],
    tuple[PlanCondition, ...],
]:
    roles = _role_by_name(normalized)
    hotshotxl_class = _role_class(roles, "hotshotxl_motion_model", "HotshotXLLoader")
    animatediff_class = _role_class(
        roles,
        "animatediff_context",
        "ADE_AnimateDiffLoaderWithContext",
    )
    latent_class = _role_class(roles, "latent_source", "EmptyLatentImage")
    sampler_class = _role_class(roles, "sampler", "KSampler")
    decoder_class = _role_class(roles, "decoder", "VAEDecode")
    terminal_class = _role_class(roles, "video_terminal", "VHS_VideoCombine")

    hotshotxl = _role_socket(
        "hotshotxl_motion_model",
        hotshotxl_class,
        output_name="MOTION_MODEL",
    )
    animatediff_model_in = _role_socket(
        "animatediff_context",
        animatediff_class,
        input_name="model",
    )
    animatediff_motion_in = _role_socket(
        "animatediff_context",
        animatediff_class,
        input_name="motion_model",
    )
    animatediff_model_out = _role_socket(
        "animatediff_context",
        animatediff_class,
        output_name="MODEL",
    )
    latent = _role_socket("latent_source", latent_class)
    sampler_model_in = _role_socket("sampler", sampler_class, input_name="model")
    sampler_samples = _role_socket("sampler", sampler_class, output_name="LATENT")
    decoder_samples = _role_socket("decoder", decoder_class, input_name="samples")
    decoder_images = _role_socket("decoder", decoder_class, output_name="IMAGE")
    terminal_images = _role_socket("video_terminal", terminal_class, input_name="images")

    done_conditions = (
        PlanCondition(
            condition_id="hotshotxl.motion_model.present",
            kind="required_class",
            class_type=hotshotxl_class,
            message="HotShotXL motion model loader must be present.",
            details={"role": "hotshotxl_motion_model"},
        ),
        PlanCondition(
            condition_id="animatediff.context.present",
            kind="required_class",
            class_type=animatediff_class,
            message="AnimateDiff context loader must be present.",
            details={"role": "animatediff_context"},
        ),
        PlanCondition(
            condition_id="animatediff.motion_model.edge",
            kind="direct_edge",
            source=hotshotxl,
            target=animatediff_motion_in,
            input_name="motion_model",
            message="HotShotXL motion model must feed the AnimateDiff context.",
            details={"source_role": "hotshotxl_motion_model", "target_role": "animatediff_context"},
        ),
        PlanCondition(
            condition_id="sampler.uses_animatediff_model",
            kind="direct_edge_or_reachable_path",
            source=animatediff_model_out,
            target=sampler_model_in,
            input_name="model",
            message="Sampler model input must consume the AnimateDiff-wrapped model path.",
            details={"source_role": "animatediff_context", "target_role": "sampler"},
        ),
        PlanCondition(
            condition_id="hotshotxl.active_8_frame_latent_path",
            kind="batch_frame_count",
            source=latent,
            target=_role_socket("sampler", sampler_class, input_name="latent_image"),
            class_type=latent_class,
            input_name="latent_image",
            expected=8,
            message="HotShotXL video generation must use an active 8-frame latent path.",
            details={
                "field": "widget_2",
                "role": "latent_source",
                "target_role": "sampler",
            },
        ),
        PlanCondition(
            condition_id="video.decoded_frames",
            kind="direct_edge_or_reachable_path",
            source=sampler_samples,
            target=decoder_samples,
            input_name="samples",
            message="Sampler latent output must be decoded into frames.",
            details={"source_role": "sampler", "target_role": "decoder"},
        ),
        PlanCondition(
            condition_id="video.terminal.consumes_decoded_frames",
            kind="terminal_consumes",
            source=decoder_images,
            target=terminal_images,
            input_name="images",
            message="A video terminal must consume decoded frames.",
            details={"source_role": "decoder", "target_role": "video_terminal"},
        ),
    )
    active_path_conditions = (
        PlanCondition(
            condition_id="video.output_domain.active",
            kind="active_output_domain",
            expected="VIDEO",
            message="The active terminal output must be video-domain.",
            details={"terminal_role": "video_terminal"},
        ),
    )
    blocked_if = (
        PlanCondition(
            condition_id="video.image_terminal.active",
            kind="active_output_domain",
            criticality="critical",
            expected="IMAGE",
            message="A still-image terminal must not be the active output for this video plan.",
            details={"blocked_domain": "IMAGE"},
        ),
    )
    return done_conditions, active_path_conditions, blocked_if


def _hotshotxl_required_steps(
    normalized: NormalizedPrecedentEvidence,
    conditions: tuple[PlanCondition, ...],
) -> tuple[PlanStep, ...]:
    condition_by_id = {condition.condition_id: condition for condition in conditions}
    roles = _role_by_name(normalized)

    def role_step(
        *,
        step_id: str,
        role: str,
        kind: str,
        condition_ids: tuple[str, ...],
        values: Mapping[str, Any] | None = None,
    ) -> PlanStep:
        role_evidence = roles[role]
        class_type = role_evidence.class_types[0] if role_evidence.class_types else None
        return PlanStep(
            step_id=step_id,
            kind=kind,
            class_type=class_type,
            assign_to=role,
            schema_source=str(normalized.schema_provenance.get(class_type or "", "not_available")),
            runtime_availability=str(normalized.runtime_provenance.get(class_type or "", "not_checked")),
            inputs=_thaw_jsonish(role_evidence.input_sockets),
            values=values or {},
            conditions=tuple(condition_by_id[condition_id] for condition_id in condition_ids),
            evidence_refs=role_evidence.evidence_refs,
        )

    latent_values: dict[str, Any] = {}
    frame_evidence = _as_mapping(_thaw_jsonish(normalized.widget_evidence)).get(
        "latent_source.batch_size",
    )
    if isinstance(frame_evidence, Mapping) and "value" in frame_evidence:
        latent_values["batch_size"] = frame_evidence["value"]

    return (
        role_step(
            step_id="step.hotshotxl_motion_model",
            role="hotshotxl_motion_model",
            kind="add_or_bind_node",
            condition_ids=("hotshotxl.motion_model.present", "animatediff.motion_model.edge"),
            values={
                "models": list(roles["hotshotxl_motion_model"].models),
            },
        ),
        role_step(
            step_id="step.animatediff_context",
            role="animatediff_context",
            kind="add_or_bind_node",
            condition_ids=(
                "animatediff.context.present",
                "animatediff.motion_model.edge",
                "sampler.uses_animatediff_model",
            ),
        ),
        role_step(
            step_id="step.sampler_model_path",
            role="sampler",
            kind="wire_path",
            condition_ids=("sampler.uses_animatediff_model",),
        ),
        role_step(
            step_id="step.active_8_frame_latent_path",
            role="latent_source",
            kind="set_value",
            condition_ids=("hotshotxl.active_8_frame_latent_path",),
            values=latent_values,
        ),
        role_step(
            step_id="step.decoded_frames",
            role="decoder",
            kind="wire_path",
            condition_ids=("video.decoded_frames",),
        ),
        role_step(
            step_id="step.video_terminal_consumption",
            role="video_terminal",
            kind="add_or_bind_terminal",
            condition_ids=("video.terminal.consumes_decoded_frames",),
        ),
    )


def build_execution_plan(
    *,
    research_result: Any = None,
    classify_result: Any = None,
    task: Any = None,
    graph_facts: Any = None,
    graph: Mapping[str, Any] | None = None,
    current_python: str | None = None,
    source_graph_hash: str | None = None,
    candidate_graph_hash: str | None = None,
) -> ExecutionPlan | None:
    """Build an M1 ``ExecutionPlan`` for narrow precedent-backed video patterns.

    M2 deliberately supports only the deterministic HotShotXL 8-frame video
    path. Unsupported or insufficient precedent evidence returns ``None`` so
    later wiring can continue without plan enforcement.
    """

    del current_python

    normalized = _normalize_precedent_evidence(
        research_result,
        classify_result=classify_result,
        task=task,
        graph_facts=graph_facts,
    )
    if normalized is None:
        return None
    if "HotShotXL" not in normalized.technologies or "video" not in normalized.media_domains:
        return None
    frame_evidence = _as_mapping(_thaw_jsonish(normalized.widget_evidence)).get(
        "latent_source.batch_size",
    )
    if not isinstance(frame_evidence, Mapping) or frame_evidence.get("value") != 8:
        return None

    selected_precedent = _selected_precedent_payload(research_result, normalized)
    selected_precedent_id = _selected_precedent_id(selected_precedent, normalized)
    normalized_payload = normalized.to_dict()
    plan_id = f"plan.hotshotxl_8f.{_stable_json_hash((task, selected_precedent_id, normalized_payload))}"

    done_conditions, active_path_conditions, blocked_if = _hotshotxl_conditions(normalized)
    required_steps = _hotshotxl_required_steps(normalized, done_conditions)
    computed_source_hash = source_graph_hash
    if computed_source_hash is None and graph is not None:
        computed_source_hash = structural_graph_hash(graph)

    return ExecutionPlan(
        plan_id=plan_id,
        goal="Generate an active 8-frame HotShotXL video output.",
        source_graph_hash=computed_source_hash,
        candidate_graph_hash=candidate_graph_hash,
        research_result_hash=_stable_json_hash(_as_mapping(research_result) or normalized_payload),
        selected_precedent_id=selected_precedent_id,
        selected_precedent=selected_precedent,
        role_bindings=_role_bindings(normalized, graph),
        required_steps=required_steps,
        done_conditions=done_conditions,
        active_path_conditions=active_path_conditions,
        blocked_if=blocked_if,
        schema_provenance={
            **_thaw_jsonish(normalized.schema_provenance),
            "execution_plan_builder": _plan_provenance(normalized),
        },
        runtime_provenance=_thaw_jsonish(normalized.runtime_provenance),
    )


def detect_named_external_technologies(*values: Any) -> tuple[str, ...]:
    """Return known user-named external workflow technologies found in values."""
    seen: set[str] = set()
    detected: list[str] = []
    for text in _iter_text(values):
        for name, pattern in _NAMED_TECHNOLOGY_PATTERNS:
            if name not in seen and pattern.search(text):
                seen.add(name)
                detected.append(name)
    return tuple(detected)


def _has_planning_signal(*values: Any) -> bool:
    for text in _iter_text(values):
        if _PLANNING_SIGNAL_RE.search(text):
            return True
    return False


def needs_precedent_plan(
    classify_result: Any,
    task: Any = None,
    graph_facts: Any = None,
) -> bool:
    """Return whether an executor request should build an ExecutionPlan.

    The normalized/effective route is the authority. Only qualifying ``adapt``
    requests may plan; all non-adapt routes bypass planning even when legacy
    booleans or classifier metadata still mention research, implementation, or
    external technologies.
    """

    route = _effective_route(classify_result)
    if route in _NON_PLANNING_ROUTES:
        return False
    if route != "adapt":
        return False

    signal_values = (
        task,
        tuple(_iter_classify_signal_text(classify_result)),
        tuple(_iter_graph_fact_text(graph_facts)),
    )
    if _has_planning_signal(signal_values):
        return True
    return bool(detect_named_external_technologies(signal_values))


__all__ = [
    "build_execution_plan",
    "detect_named_external_technologies",
    "needs_precedent_plan",
]
