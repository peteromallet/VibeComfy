"""Advisory edit-target and seed-suggestion tools for agent judgment.

B5/B14 target/seed suggestion tools. These are READ-ONLY, ADVISORY helpers an
agent may call explicitly while planning a change to an existing graph or a
green-field build:

* ``rank_edit_targets(graph, intent)`` — rank existing graph nodes as
  candidate change targets, with per-candidate scoring factors and a
  descriptive (non-directive) reason.
* ``suggest_seed_nodes(intent, constraints)`` — suggest node classes to seed
  a build from, again with factors and reasons.
* ``diagnose_existing_tweak_ranking(graph, query_text)`` — OPTIONAL
  diagnostic mirror of the legacy
  ``comfy_nodes.agent._frag_batch_memory._existing_parameter_tweak_targets_from_graph``
  scoring (same points, same ``"{class_type} [{node_id}] ({preview})"`` target
  strings, same graph-iteration order and deduplication) so agents can
  cross-check rankings. The legacy module is left untouched; this is a
  repurposed, self-contained copy.

Design contract
---------------
* Advisory only: every result exposes scores, a per-factor breakdown, and
  descriptive reasons. Results NEVER contain directive language ("must
  edit", "do not add", "land the change", ...). The agent decides.
* Explicit-call gate: all three tools REFUSE (``ToolStatus.REFUSED``) unless
  invoked with ``explicit=True``. Nothing in the pipeline imports this module
  or injects its output into an authoring package automatically — an implicit
  call is refused in code, not merely documented away.
* Typed cases (``SuggestionCase``): ``existing-node`` (candidates produced),
  ``empty-graph`` (no nodes to rank or seed into), ``no-candidate`` (nodes or
  intent present, but nothing qualifies).

Scoring factors (shared with the legacy ranking)
-------------------------------------------------
+5  ``class_parameter_term``  class name contains a parameter-tweak term
+4  ``field_parameter_term``  a field name contains a parameter-tweak term
+4  ``class_intent_match``    an intent token (len >= 5) appears in the class
+3  ``field_intent_match``    an intent token (len >= 5) appears in a field
+3  ``editable_fields``       node exposes compact/widget fields
+8  ``controlnet_heuristic``  ACN_AdvancedControlNetApply + "controlnet" intent
-6  ``non_editable_sink``     output/sink node (MarkdownNote/Preview3D/...)

Seed suggestions add capability-match (+5 per matched intent phrase), plus
constraint factors: ``output_type_match`` (+2), ``output_type_mismatch`` (-2),
``preferred_class`` (+3).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from vibecomfy.porting.widgets.settings_contract import node_settings_for

from .tool_contracts import ToolDiagnostic, ToolResult, ToolStatus

from vibecomfy.ingest.door_access import door_get_nodes, door_get_widgets_values
# Same parameter-term set the legacy tweak ranking keys on.
PARAMETER_TWEAK_TARGET_TERMS = (
    "detail",
    "frame",
    "fps",
    "rate",
    "step",
    "strength",
    "cfg",
    "seed",
    "scale",
    "denoise",
    "resolution",
    "width",
    "height",
    "duration",
    "quality",
    "prompt",
    "format",
    "codec",
)

_NON_EDITABLE_SINK_CLASSES = frozenset(
    {"MarkdownNote", "Preview3D", "SaveVideo", "LoadImage"}
)


class SuggestionCase(StrEnum):
    """Typed situation the suggestion tool observed."""

    EXISTING_NODE = "existing-node"
    EMPTY_GRAPH = "empty-graph"
    NO_CANDIDATE = "no-candidate"


@dataclass(frozen=True, slots=True)
class ScoringFactor:
    """One named scoring contribution with a human-readable detail."""

    points: int
    name: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"points": self.points, "name": self.name, "detail": self.detail}


@dataclass(frozen=True, slots=True)
class EditTargetCandidate:
    """A ranked existing-node candidate with its factor breakdown."""

    node_id: str
    class_type: str
    score: int
    preview: str
    factors: tuple[ScoringFactor, ...]
    reason: str

    @property
    def label(self) -> str:
        """Legacy-compatible ``class_type [node_id] (preview)`` label."""

        return f"{self.class_type} [{self.node_id}] ({self.preview})"

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "class_type": self.class_type,
            "score": self.score,
            "preview": self.preview,
            "factors": [factor.to_dict() for factor in self.factors],
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class SeedSuggestion:
    """A suggested seed node class with its factor breakdown."""

    class_type: str
    role: str
    score: int
    factors: tuple[ScoringFactor, ...]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "class_type": self.class_type,
            "role": self.role,
            "score": self.score,
            "factors": [factor.to_dict() for factor in self.factors],
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class _SeedEntry:
    class_type: str
    role: str


def _seeds(*pairs: tuple[str, str]) -> tuple[_SeedEntry, ...]:
    return tuple(_SeedEntry(class_type, role) for class_type, role in pairs)


# Capability phrases -> seed class candidates. Matching is deterministic:
# every phrase present in the casefolded intent contributes +5 to each of its
# classes. Core ComfyUI class types only.
_SEED_INDEX: tuple[tuple[str, tuple[_SeedEntry, ...]], ...] = (
    (
        "text to image",
        _seeds(
            ("CLIPTextEncode", "conditioning"),
            ("KSampler", "sampler"),
            ("VAEDecode", "decoder"),
        ),
    ),
    (
        "txt2img",
        _seeds(
            ("CLIPTextEncode", "conditioning"),
            ("KSampler", "sampler"),
            ("VAEDecode", "decoder"),
        ),
    ),
    (
        "text-to-image",
        _seeds(
            ("CLIPTextEncode", "conditioning"),
            ("KSampler", "sampler"),
            ("VAEDecode", "decoder"),
        ),
    ),
    (
        "image to image",
        _seeds(
            ("VAEEncode", "encoder"),
            ("KSampler", "sampler"),
            ("VAEDecode", "decoder"),
        ),
    ),
    (
        "img2img",
        _seeds(
            ("VAEEncode", "encoder"),
            ("KSampler", "sampler"),
            ("VAEDecode", "decoder"),
        ),
    ),
    (
        "image-to-image",
        _seeds(
            ("VAEEncode", "encoder"),
            ("KSampler", "sampler"),
            ("VAEDecode", "decoder"),
        ),
    ),
    (
        "upscale",
        _seeds(
            ("UpscaleModelLoader", "loader"),
            ("ImageUpscaleWithModel", "image-op"),
        ),
    ),
    (
        "hi-res",
        _seeds(
            ("UpscaleModelLoader", "loader"),
            ("ImageUpscaleWithModel", "image-op"),
        ),
    ),
    (
        "hires",
        _seeds(
            ("UpscaleModelLoader", "loader"),
            ("ImageUpscaleWithModel", "image-op"),
        ),
    ),
    (
        "controlnet",
        _seeds(
            ("ControlNetLoader", "loader"),
            ("ControlNetApplyAdvanced", "conditioning"),
        ),
    ),
    (
        "pose",
        _seeds(
            ("ControlNetLoader", "loader"),
            ("ControlNetApplyAdvanced", "conditioning"),
        ),
    ),
    (
        "inpaint",
        _seeds(
            ("VAEEncodeForInpaint", "encoder"),
            ("InpaintModelConditioning", "conditioning"),
        ),
    ),
    (
        "outpaint",
        _seeds(
            ("VAEEncodeForInpaint", "encoder"),
            ("InpaintModelConditioning", "conditioning"),
        ),
    ),
    (
        "blur",
        _seeds(("ImageBlur", "image-op")),
    ),
    (
        "sharpen",
        _seeds(("ImageSharpen", "image-op")),
    ),
    (
        "resize",
        _seeds(("ImageScaleBy", "image-op"), ("ImageScale", "image-op")),
    ),
    (
        "resolution",
        _seeds(("ImageScaleBy", "image-op"), ("ImageScale", "image-op")),
    ),
    (
        "scale up",
        _seeds(("ImageScaleBy", "image-op"), ("ImageScale", "image-op")),
    ),
    (
        "background",
        _seeds(("ImageRemoveBackground", "image-op")),
    ),
    (
        "remove background",
        _seeds(("ImageRemoveBackground", "image-op")),
    ),
    (
        "video",
        _seeds(("SaveVideo", "output")),
    ),
    (
        "animation",
        _seeds(("SaveVideo", "output")),
    ),
    (
        "animate",
        _seeds(("SaveVideo", "output")),
    ),
    (
        "conditioning",
        _seeds(
            ("CLIPTextEncode", "conditioning"),
            ("ControlNetApplyAdvanced", "conditioning"),
        ),
    ),
    (
        "seed",
        _seeds(("KSampler", "sampler")),
    ),
    (
        "variation",
        _seeds(("KSampler", "sampler")),
    ),
    (
        "random",
        _seeds(("KSampler", "sampler")),
    ),
)


# ── graph / node introspection (mirrors the legacy ranking source) ──────────


def _graph_node_count(graph: Any) -> int:
    if not isinstance(graph, Mapping):
        return 0
    nodes = door_get_nodes(graph)
    if isinstance(nodes, Mapping):
        return len(nodes)
    if isinstance(nodes, list):
        return sum(1 for node in nodes if isinstance(node, Mapping))
    return 0


def _iter_node_items(graph: Mapping[str, Any]):
    """Yield ``(node_id, node)`` pairs exactly like the legacy ranking source."""

    nodes = door_get_nodes(graph)
    if isinstance(nodes, Mapping):
        for node_id, node in nodes.items():
            if isinstance(node, Mapping):
                yield str(node_id), node
        return
    if isinstance(nodes, list):
        for index, node in enumerate(nodes):
            if isinstance(node, Mapping):
                yield str(node.get("id") or index), node


def _node_class_type(node: Mapping[str, Any]) -> str:
    return str(node.get("class_type") or node.get("type") or "").strip()


def _scalar_input_field_names(inputs: Any) -> list[str]:
    """Unconnected scalar input names (the legacy structural reading)."""

    names: list[str] = []
    if isinstance(inputs, Mapping):
        names = [
            str(name)
            for name, value in inputs.items()
            if not isinstance(value, (Mapping, list, tuple))
        ]
    elif isinstance(inputs, list):
        for input_spec in inputs:
            if not isinstance(input_spec, Mapping):
                continue
            if input_spec.get("link") is not None:
                continue
            name = input_spec.get("name")
            if isinstance(name, str) and name:
                names.append(name)
    return names


def _compact_field_previews(
    node: Mapping[str, Any], class_type: str
) -> tuple[list[str], bool]:
    """Compact field names via the shared settings contract, with enum hints."""

    previews: list[str] = []
    try:
        info = node_settings_for(node, class_type)
    except Exception:
        return previews, False
    if not info.fields:
        return previews, False
    for field in info.fields:
        name = field.name
        if field.choices and not name.startswith("widget_"):
            choices = list(field.choices)
            if len(choices) <= 3:
                enum_hint = "|".join(choices)
            else:
                shown = choices[:3]
                remaining = len(choices) - 3
                enum_hint = "|".join(shown) + f"|+{remaining}"
            name = f"{name}[{enum_hint}]"
        previews.append(name)
    return previews, True


def _widget_fallback_fields(node: Mapping[str, Any]) -> tuple[list[str], int | None]:
    """Legacy widget fallback: ``widgets``/``widgets_values``/``raw_widgets``."""

    widget_fields: list[str] = []
    raw_widget_count: int | None = None
    widgets = node.get("widgets")
    raw_widgets = node.get("raw_widgets")
    if isinstance(widgets, Mapping):
        widget_fields = [str(name) for name in sorted(widgets, key=str)]
    elif isinstance(widgets, list):
        widget_fields = [
            str(widget.get("name") or f"widget_{index}")
            for index, widget in enumerate(widgets)
            if isinstance(widget, Mapping)
        ]
    widget_values = door_get_widgets_values(node)
    if not widget_fields and isinstance(widget_values, list):
        widget_fields = [f"widget_{index}" for index in range(min(len(widget_values), 4))]
    if isinstance(raw_widgets, Mapping):
        values = raw_widgets.get("values")
        if isinstance(values, list):
            raw_widget_count = len(values)
    elif raw_widgets is not None:
        values = getattr(raw_widgets, "values", None)
        if isinstance(values, list):
            raw_widget_count = len(values)
    return widget_fields, raw_widget_count


def _assemble_previews(
    node: Mapping[str, Any], class_type: str
) -> tuple[list[str], bool, bool, int | None]:
    """Return ``(previews, have_compact, has_widget_fields, raw_widget_count)``.

    Mirrors the legacy field assembly: compact names first (with scalar inputs
    merged, deduped), widget fallback otherwise.
    """

    input_fields = _scalar_input_field_names(node.get("inputs"))
    compact_previews, have_compact_names = _compact_field_previews(node, class_type)
    widget_fields, raw_widget_count = _widget_fallback_fields(node)
    if have_compact_names:
        merged: list[str] = []
        compact_set = {preview.split("[")[0] for preview in compact_previews}
        for name in input_fields:
            if name not in compact_set:
                merged.append(name)
        merged.extend(compact_previews)
        return merged, True, bool(widget_fields), raw_widget_count
    previews = input_fields + widget_fields
    if raw_widget_count and not widget_fields:
        previews.extend(
            f"widget_{index}" for index in range(min(raw_widget_count, 4))
        )
    return previews, False, bool(widget_fields), raw_widget_count


def _score_node(
    node: Mapping[str, Any],
    node_id: str,
    class_type: str,
    query_text: str,
) -> EditTargetCandidate | None:
    """Score one node with the legacy factor set; ``None`` when not editable."""

    previews, have_compact_names, has_widget_fields, raw_widget_count = (
        _assemble_previews(node, class_type)
    )
    if not previews:
        return None
    preview = ", ".join(previews)
    class_text = class_type.casefold()
    field_text = " ".join(previews).casefold()

    factors: list[ScoringFactor] = []
    score = 0

    matched_class_terms = sorted(
        {term for term in PARAMETER_TWEAK_TARGET_TERMS if term in class_text}
    )
    if matched_class_terms:
        score += 5
        factors.append(
            ScoringFactor(
                5,
                "class_parameter_term",
                "class name contains parameter term(s): " + ", ".join(matched_class_terms),
            )
        )
    matched_field_terms = sorted(
        {term for term in PARAMETER_TWEAK_TARGET_TERMS if term in field_text}
    )
    if matched_field_terms:
        score += 4
        factors.append(
            ScoringFactor(
                4,
                "field_parameter_term",
                "field name(s) contain parameter term(s): " + ", ".join(matched_field_terms),
            )
        )
    query_tokens = [token for token in query_text.split() if len(token) >= 5]
    matched_class_tokens = sorted({token for token in query_tokens if token in class_text})
    if matched_class_tokens:
        score += 4
        factors.append(
            ScoringFactor(
                4,
                "class_intent_match",
                "intent term(s) appear in the class name: " + ", ".join(matched_class_tokens),
            )
        )
    matched_field_tokens = sorted({token for token in query_tokens if token in field_text})
    if matched_field_tokens:
        score += 3
        factors.append(
            ScoringFactor(
                3,
                "field_intent_match",
                "intent term(s) appear in a field name: " + ", ".join(matched_field_tokens),
            )
        )
    if have_compact_names or has_widget_fields or raw_widget_count:
        score += 3
        factors.append(
            ScoringFactor(3, "editable_fields", "node exposes editable field(s): " + preview)
        )
    if class_type == "ACN_AdvancedControlNetApply" and "controlnet" in query_text:
        score += 8
        factors.append(
            ScoringFactor(
                8,
                "controlnet_heuristic",
                "ControlNet apply node matches controlnet intent",
            )
        )
    if class_type in _NON_EDITABLE_SINK_CLASSES:
        score -= 6
        factors.append(
            ScoringFactor(
                -6,
                "non_editable_sink",
                "output/sink node is a weak candidate for parameter changes",
            )
        )

    return EditTargetCandidate(
        node_id=node_id,
        class_type=class_type,
        score=score,
        preview=preview,
        factors=tuple(factors),
        reason="; ".join(factor.detail for factor in factors),
    )


# ── ToolResult helpers ───────────────────────────────────────────────────────


def _refused_result(tool_name: str) -> ToolResult:
    return ToolResult(
        tool_name=tool_name,
        status=ToolStatus.REFUSED,
        result=None,
        diagnostics=(
            ToolDiagnostic(
                code="suggestion_tool_requires_explicit_call",
                message=(
                    "Target/seed suggestion tools run only on explicit agent "
                    "calls; pass explicit=True to invoke one."
                ),
                details={"explicit": False},
            ),
        ),
    )


def _invalid_result(tool_name: str, code: str, message: str) -> ToolResult:
    return ToolResult(
        tool_name=tool_name,
        status=ToolStatus.INVALID_REQUEST,
        result=None,
        diagnostics=(ToolDiagnostic(code=code, message=message),),
    )


def _no_results_result(
    tool_name: str, case: SuggestionCase, payload: Mapping[str, Any]
) -> ToolResult:
    return ToolResult(
        tool_name=tool_name,
        status=ToolStatus.NO_RESULTS,
        result={"case": case.value, **dict(payload)},
    )


def _constraint_terms(value: Any, label: str) -> tuple[str, ...] | None:
    """Normalize a list-of-strings constraint; ``None`` means invalid."""

    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        return None
    terms: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            return None
        terms.append(item.strip().casefold())
    return tuple(terms)


# ── public tools ─────────────────────────────────────────────────────────────


def rank_edit_targets(
    graph: Any,
    intent: str,
    *,
    explicit: bool = False,
    max_targets: int = 4,
) -> ToolResult:
    """Rank existing graph nodes as candidate change targets (advisory).

    Scores every node exposing editable fields with the factor set described
    in the module docstring and returns the top ``max_targets`` candidates,
    each with its factor breakdown and a descriptive reason. The output is
    purely advisory: it never instructs the agent to edit anything.

    Typed cases (``result["case"]``):
    * ``existing-node`` — candidates produced (status ``ok``)
    * ``empty-graph`` — the graph has no nodes to rank (status ``no_results``)
    * ``no-candidate`` — nodes exist but none exposes editable fields
      (status ``no_results``)

    Runs only on explicit agent calls: without ``explicit=True`` the result is
    ``REFUSED`` so nothing can auto-inject this tool into an authoring path.
    """

    if not explicit:
        return _refused_result("rank_edit_targets")
    if not isinstance(intent, str) or not intent.strip():
        return _invalid_result(
            "rank_edit_targets", "invalid_intent", "`intent` must be a non-empty string."
        )
    if isinstance(max_targets, bool) or not isinstance(max_targets, int) or max_targets < 1:
        return _invalid_result(
            "rank_edit_targets",
            "invalid_max_targets",
            "`max_targets` must be a positive integer.",
        )
    if not isinstance(graph, Mapping) or _graph_node_count(graph) == 0:
        return _no_results_result(
            "rank_edit_targets",
            SuggestionCase.EMPTY_GRAPH,
            {"intent": intent, "candidates": [], "reason": "The graph has no nodes."},
        )

    query_text = intent.casefold()
    candidates: list[EditTargetCandidate] = []
    for node_id, node in _iter_node_items(graph):
        class_type = _node_class_type(node)
        if not class_type:
            continue
        candidate = _score_node(node, node_id, class_type, query_text)
        if candidate is None:
            continue
        candidates.append(candidate)
    if not candidates:
        return _no_results_result(
            "rank_edit_targets",
            SuggestionCase.NO_CANDIDATE,
            {
                "intent": intent,
                "candidates": [],
                "reason": "No node exposes editable fields, so none qualify for ranking.",
            },
        )

    candidates.sort(key=lambda candidate: (-candidate.score, candidate.label))
    top = candidates[:max_targets]
    return ToolResult(
        tool_name="rank_edit_targets",
        status=ToolStatus.OK,
        result={
            "case": SuggestionCase.EXISTING_NODE.value,
            "intent": intent,
            "total_nodes": _graph_node_count(graph),
            "candidates": [candidate.to_dict() for candidate in top],
        },
    )


def suggest_seed_nodes(
    intent: str,
    constraints: Any = None,
    *,
    graph: Any = None,
    explicit: bool = False,
    max_suggestions: int = 4,
) -> ToolResult:
    """Suggest node classes to seed a build from (advisory).

    Matches capability phrases from ``intent`` against a fixed seed index and
    scores each matched class; ``constraints`` may carry ``output_type``
    (str), ``preferred_classes`` (list of class-name substrings), and
    ``exclude_classes`` (list of class-name substrings) to tilt the ranking.
    Results carry factors and reasons only — no build directives.

    Typed cases (``result["case"]``):
    * ``existing-node`` — the graph already holds nodes; seeds are additive
      candidates (status ``ok``)
    * ``empty-graph`` — no graph (or an empty one); seeds are starting points
      (status ``ok``)
    * ``no-candidate`` — no seed class matches the intent (status
      ``no_results``)

    Runs only on explicit agent calls (``explicit=True``); implicit calls are
    refused.
    """

    if not explicit:
        return _refused_result("suggest_seed_nodes")
    if not isinstance(intent, str) or not intent.strip():
        return _invalid_result(
            "suggest_seed_nodes", "invalid_intent", "`intent` must be a non-empty string."
        )
    if constraints is None:
        constraints = {}
    if not isinstance(constraints, Mapping):
        return _invalid_result(
            "suggest_seed_nodes",
            "invalid_constraints",
            "`constraints` must be an object.",
        )
    if isinstance(max_suggestions, bool) or not isinstance(max_suggestions, int) or max_suggestions < 1:
        return _invalid_result(
            "suggest_seed_nodes",
            "invalid_max_suggestions",
            "`max_suggestions` must be a positive integer.",
        )

    output_type = constraints.get("output_type")
    if output_type is not None:
        if not isinstance(output_type, str) or not output_type.strip():
            return _invalid_result(
                "suggest_seed_nodes",
                "invalid_output_type",
                "`constraints.output_type` must be a string when provided.",
            )
        output_type = output_type.strip().casefold()
    preferred = _constraint_terms(constraints.get("preferred_classes"), "preferred_classes")
    if preferred is None:
        return _invalid_result(
            "suggest_seed_nodes",
            "invalid_preferred_classes",
            "`constraints.preferred_classes` must be a list of strings when provided.",
        )
    excluded = _constraint_terms(constraints.get("exclude_classes"), "exclude_classes")
    if excluded is None:
        return _invalid_result(
            "suggest_seed_nodes",
            "invalid_exclude_classes",
            "`constraints.exclude_classes` must be a list of strings when provided.",
        )

    query_text = intent.casefold()
    collected: dict[str, tuple[str, list[ScoringFactor]]] = {}
    matched_phrases: set[str] = set()
    for phrase, seeds in _SEED_INDEX:
        if phrase not in query_text:
            continue
        matched_phrases.add(phrase)
        for seed in seeds:
            _role, factors = collected.setdefault(seed.class_type, (seed.role, []))
            factors.append(
                ScoringFactor(
                    5,
                    "capability_match",
                    f"intent term {phrase!r} matches {seed.class_type} ({seed.role})",
                )
            )
    for class_type in list(collected):
        if any(term in class_type.casefold() for term in excluded):
            del collected[class_type]
    if not collected:
        reason = (
            "No seed class matches any capability phrase in the intent."
            if not matched_phrases
            else "All matching seed classes are excluded by constraints."
        )
        return _no_results_result(
            "suggest_seed_nodes",
            SuggestionCase.NO_CANDIDATE,
            {"intent": intent, "suggestions": [], "reason": reason},
        )

    suggestions: list[SeedSuggestion] = []
    for class_type, (role, factors) in collected.items():
        score = sum(factor.points for factor in factors)
        class_lower = class_type.casefold()
        if output_type is not None:
            if output_type in class_lower:
                score += 2
                factors.append(
                    ScoringFactor(
                        2,
                        "output_type_match",
                        f"class name contains requested output type {output_type!r}",
                    )
                )
            else:
                score -= 2
                factors.append(
                    ScoringFactor(
                        -2,
                        "output_type_mismatch",
                        f"class name does not mention output type {output_type!r}",
                    )
                )
        matched_preferred = sorted({term for term in preferred if term in class_lower})
        if matched_preferred:
            score += 3
            factors.append(
                ScoringFactor(
                    3,
                    "preferred_class",
                    "class name contains preferred term(s): " + ", ".join(matched_preferred),
                )
            )
        suggestions.append(
            SeedSuggestion(
                class_type=class_type,
                role=role,
                score=score,
                factors=tuple(factors),
                reason="; ".join(factor.detail for factor in factors),
            )
        )
    suggestions.sort(key=lambda suggestion: (-suggestion.score, suggestion.class_type))
    top = suggestions[:max_suggestions]
    case = (
        SuggestionCase.EXISTING_NODE
        if _graph_node_count(graph) > 0
        else SuggestionCase.EMPTY_GRAPH
    )
    return ToolResult(
        tool_name="suggest_seed_nodes",
        status=ToolStatus.OK,
        result={
            "case": case.value,
            "intent": intent,
            "matched_phrases": sorted(matched_phrases),
            "suggestions": [suggestion.to_dict() for suggestion in top],
        },
    )


def diagnose_existing_tweak_ranking(
    graph: Any,
    query_text: str,
    *,
    explicit: bool = False,
    max_targets: int = 4,
) -> ToolResult:
    """OPTIONAL diagnostic mirror of the legacy tweak-target ranking.

    Replicates ``_frag_batch_memory._existing_parameter_tweak_targets_from_graph``
    scoring exactly — same points, same ``"{class_type} [{node_id}] ({preview})"``
    target strings, same graph-iteration order (the legacy source does not sort;
    its caller does) and same label deduplication — so an agent can cross-check
    the legacy ranking against ``rank_edit_targets``. The legacy module is not
    touched or imported by this module.

    Returns per-target scores and factor breakdowns; case is ``existing-node``
    when targets exist, otherwise ``empty-graph``/``no-candidate`` with
    ``no_results`` status. Runs only on explicit agent calls.
    """

    if not explicit:
        return _refused_result("diagnose_existing_tweak_ranking")
    if not isinstance(query_text, str) or not query_text.strip():
        return _invalid_result(
            "diagnose_existing_tweak_ranking",
            "invalid_query_text",
            "`query_text` must be a non-empty string.",
        )
    if isinstance(max_targets, bool) or not isinstance(max_targets, int) or max_targets < 1:
        return _invalid_result(
            "diagnose_existing_tweak_ranking",
            "invalid_max_targets",
            "`max_targets` must be a positive integer.",
        )
    if not isinstance(graph, Mapping) or _graph_node_count(graph) == 0:
        return _no_results_result(
            "diagnose_existing_tweak_ranking",
            SuggestionCase.EMPTY_GRAPH,
            {
                "query_text": query_text,
                "targets": [],
                "reason": "The graph has no nodes, so the legacy ranking yields no targets.",
            },
        )

    normalized_query = query_text.casefold()
    seen: set[str] = set()
    scored: list[tuple[int, str, EditTargetCandidate]] = []
    for node_id, node in _iter_node_items(graph):
        class_type = _node_class_type(node)
        if not class_type:
            continue
        candidate = _score_node(node, node_id, class_type, normalized_query)
        if candidate is None:
            continue
        if candidate.label in seen:
            continue
        seen.add(candidate.label)
        scored.append((candidate.score, candidate.label, candidate))
    if not scored:
        return _no_results_result(
            "diagnose_existing_tweak_ranking",
            SuggestionCase.NO_CANDIDATE,
            {
                "query_text": query_text,
                "targets": [],
                "reason": "No node exposes editable fields, so the legacy ranking yields no targets.",
            },
        )

    targets = [
        {
            "target": label,
            "score": score,
            "factors": [factor.to_dict() for factor in candidate.factors],
        }
        for score, label, candidate in scored[:max_targets]
    ]
    return ToolResult(
        tool_name="diagnose_existing_tweak_ranking",
        status=ToolStatus.OK,
        result={
            "case": SuggestionCase.EXISTING_NODE.value,
            "query_text": query_text,
            "targets": targets,
            "legacy_format": "{class_type} [{node_id}] ({preview})",
        },
    )


__all__ = [
    "EditTargetCandidate",
    "PARAMETER_TWEAK_TARGET_TERMS",
    "ScoringFactor",
    "SeedSuggestion",
    "SuggestionCase",
    "diagnose_existing_tweak_ranking",
    "rank_edit_targets",
    "suggest_seed_nodes",
]
