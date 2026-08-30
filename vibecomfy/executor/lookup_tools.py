"""Agent-invoked registry, node-schema, and ready-template lookup tools.

One line per tool, answering exactly the question the agent asked — never a
decision the agent should make:

* ``registry_lookup(node_class)`` — which pack **exactly** owns a node class,
  from the Comfy Registry (comfy.org) and ComfyUI-Manager evidence only.  No
  fuzzy "probably this pack" replacement class is ever returned: a candidate
  counts only when the authoritative tier declares the queried class in its
  ``expected_classes``.
* ``node_schema(node_class)`` — is the class available in the runtime/local
  schema providers, and what inputs/outputs can be emitted.
* ``ready_template_list(capability?)`` — shipping ready-template assets as
  direct-load inventory (explicitly NOT research evidence).
* ``ready_template_load(id)`` — load one ready-template source asset,
  path-confined to the template roots, with a stable identity and content hash.

Every tool returns a typed ``ToolResult`` (``ok | no_results | rate_limited |
timeout | unavailable | invalid_request | refused``).  A rate limit is never
"nothing exists"; a timeout is never "no evidence".

Determinism boundary: these functions do transport, existence checks, and
exactness filtering only.  They never rank alternatives, never pick a winner,
never decide whether enough evidence exists, and never inject anything into an
authoring package.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from vibecomfy.registry.pack_resolver import (
    MissingNodeResolution,
    resolve_missing_nodes,
)
from vibecomfy.registry import ready as ready_registry
from vibecomfy.schema import (
    NodeSchema,
    SchemaProvider,
    get_authoring_schema_provider,
    is_workflow_stub_schema,
    schema_for,
)

from .evidence_pack import _freeze_json, _thaw_json
from .tool_contracts import ToolDiagnostic, ToolResult, ToolStatus

# ── Tool names (stable identifiers for trace/evidence attribution) ──────────
TOOL_REGISTRY_LOOKUP = "registry_lookup"
TOOL_NODE_SCHEMA = "node_schema"
TOOL_READY_TEMPLATE_LIST = "ready_template_list"
TOOL_READY_TEMPLATE_LOAD = "ready_template_load"

# ── Registry exactness -------------------------------------------------------
# Exact pack ownership is accepted only from the two authoritative tiers.  The
# GitHub tier is search evidence (it may merely mention the class), so it can
# corroborate but never prove ownership — no inferred replacement class.
EXACT_OWNERSHIP_SOURCES = frozenset({"comfy-registry", "comfyui-manager"})

# A research stage may spend exactly one registry lookup.  The stage harness
# holds one RegistryLookupBudget per research stage and passes it to every call.
REGISTRY_LOOKUP_BUDGET_PER_STAGE = 1

_CLASS_NAME_RE = re.compile(r"^[A-Z][A-Za-z0-9_]*$")
_RATE_LIMIT_MARKERS = ("rate-limited", "rate limited", "cooldown active")
_TIMEOUT_MARKERS = ("sub-budget exceeded", "deadline")

# Ready-template source assets are Python sources; cap what we echo back so one
# oversized template cannot blow out an agent context window.
READY_CONTENT_CHAR_CAP = 256_000

# Ready-template results are direct shipping assets, never research evidence.
READY_EVIDENCE_LABEL = "direct_asset"
READY_IS_RESEARCH_EVIDENCE = False
LOOKUP_IS_RESEARCH_EVIDENCE = True


@dataclass
class RegistryLookupBudget:
    """Call-count budget for ``registry_lookup`` within one research stage.

    Defaults to one lookup per stage.  The stage harness creates one budget per
    research stage and passes the same instance to every ``registry_lookup``
    call; a call past the budget is refused, not silently downgraded.
    """

    remaining: int = REGISTRY_LOOKUP_BUDGET_PER_STAGE

    def consume(self) -> bool:
        if self.remaining <= 0:
            return False
        self.remaining -= 1
        return True

    @property
    def exhausted(self) -> bool:
        return self.remaining <= 0


# ── Small typed constructors ─────────────────────────────────────────────────

def _result(
    tool_name: str,
    status: ToolStatus,
    result: Any = None,
    diagnostics: Sequence[ToolDiagnostic] = (),
) -> ToolResult:
    return ToolResult(
        tool_name=tool_name,
        status=status,
        result=result,
        evidence_ids=(),
        diagnostics=tuple(diagnostics),
    )


def _json_safe(value: Any) -> Any:
    """Validate and detach a value for the JSON-safe ToolResult payload."""
    return _thaw_json(_freeze_json(value, "value"))


def _diagnostic(code: str, message: str, details: Mapping[str, Any] | None = None) -> ToolDiagnostic:
    return ToolDiagnostic(
        code=code,
        message=message,
        details=dict(details or {}),
    )


# ── Registry lookup ──────────────────────────────────────────────────────────

def registry_lookup(
    node_class: str,
    *,
    budget: RegistryLookupBudget | None = None,
    resolver: Callable[..., MissingNodeResolution] | None = None,
    cache_root: Path | None = None,
    deadline: float | None = None,
) -> ToolResult:
    """Answer which pack exactly owns ``node_class`` (comfy.org / Manager).

    ``budget`` is the per-research-stage call budget (default one).  ``resolver``
    is injectable for tests; it defaults to the pack-resolver machinery
    (``resolve_missing_nodes`` with ``query_intent="class_name"``).  ``deadline``
    is an absolute ``time.monotonic()`` value forwarded to the resolver.

    Returns ``ok`` with the exact-ownership candidates, ``no_results`` when no
    authoritative tier claims the class, ``rate_limited`` / ``timeout`` /
    ``unavailable`` for the corresponding transport states, ``refused`` when the
    stage budget is spent, and ``invalid_request`` for non-class queries.
    """
    tool = TOOL_REGISTRY_LOOKUP

    if not isinstance(node_class, str) or not node_class.strip():
        return _result(
            tool,
            ToolStatus.INVALID_REQUEST,
            result={"node_class": node_class, "is_research_evidence": LOOKUP_IS_RESEARCH_EVIDENCE},
            diagnostics=(_diagnostic("empty_node_class", "node_class must be a non-empty class name."),),
        )
    node_class = node_class.strip()
    if not _CLASS_NAME_RE.match(node_class):
        return _result(
            tool,
            ToolStatus.INVALID_REQUEST,
            result={"node_class": node_class, "is_research_evidence": LOOKUP_IS_RESEARCH_EVIDENCE},
            diagnostics=(
                _diagnostic(
                    "capability_query_rejected",
                    "registry_lookup answers exact pack ownership for one node class "
                    "(e.g. KSampler); capability-style queries are refused so a fuzzy "
                    "replacement class is never inferred.",
                    details={"node_class": node_class},
                ),
            ),
        )

    budget = budget or RegistryLookupBudget()
    if not budget.consume():
        return _result(
            tool,
            ToolStatus.REFUSED,
            result={"node_class": node_class, "is_research_evidence": LOOKUP_IS_RESEARCH_EVIDENCE},
            diagnostics=(
                _diagnostic(
                    "registry_budget_exhausted",
                    f"Registry batch budget is {REGISTRY_LOOKUP_BUDGET_PER_STAGE} lookup "
                    "per research stage; this stage already spent its lookup.",
                    details={"budget_per_stage": REGISTRY_LOOKUP_BUDGET_PER_STAGE},
                ),
            ),
        )

    do_resolve = resolver or resolve_missing_nodes
    try:
        resolution = do_resolve(
            node_class,
            query_intent="class_name",
            cache_root=cache_root,
            deadline=deadline,
        )
    except ValueError as exc:
        return _result(
            tool,
            ToolStatus.INVALID_REQUEST,
            result={"node_class": node_class, "is_research_evidence": LOOKUP_IS_RESEARCH_EVIDENCE},
            diagnostics=(_diagnostic("invalid_query", str(exc), {"node_class": node_class}),),
        )
    except Exception as exc:  # noqa: BLE001 - transport failure must stay typed
        return _result(
            tool,
            ToolStatus.UNAVAILABLE,
            result={"node_class": node_class, "is_research_evidence": LOOKUP_IS_RESEARCH_EVIDENCE},
            diagnostics=(
                _diagnostic(
                    "registry_lookup_unavailable",
                    f"Registry lookup failed: {type(exc).__name__}: {exc}",
                    {"error_type": type(exc).__name__},
                ),
            ),
        )

    warnings = tuple(resolution.warnings)
    exact = [
        candidate
        for candidate in resolution.candidates
        if candidate.ref.source in EXACT_OWNERSHIP_SOURCES
        and node_class in candidate.expected_classes
    ]

    base_result: dict[str, Any] = {
        "node_class": node_class,
        "query": resolution.query,
        "query_intent": resolution.query_intent,
        "exact_ownership": bool(exact),
        "candidates": [_json_safe(candidate.to_dict()) for candidate in exact],
        "sources_attempted": list(resolution.source_tiers_attempted),
        "warnings": list(warnings),
        "is_research_evidence": LOOKUP_IS_RESEARCH_EVIDENCE,
        "evidence_label": "registry_resolution",
    }

    if exact:
        return _result(tool, ToolStatus.OK, result=base_result)

    rate_limited = any(marker in warning.casefold() for marker in _RATE_LIMIT_MARKERS for warning in warnings)
    timed_out = any(marker in warning.casefold() for marker in _TIMEOUT_MARKERS for warning in warnings)

    if rate_limited:
        return _result(
            tool,
            ToolStatus.RATE_LIMITED,
            result=base_result,
            diagnostics=(
                _diagnostic(
                    "registry_rate_limited",
                    "An authoritative registry tier is rate-limited; retry after the cooldown. "
                    "This is a transport state, not absence of evidence.",
                    {"warnings": list(warnings)},
                ),
            ),
        )
    if timed_out:
        return _result(
            tool,
            ToolStatus.TIMEOUT,
            result=base_result,
            diagnostics=(
                _diagnostic(
                    "registry_timeout",
                    "Registry lookup hit its budget/deadline and returned partial evidence.",
                    {"warnings": list(warnings)},
                ),
            ),
        )

    if resolution.candidates:
        considered = sorted(
            {candidate.ref.slug for candidate in resolution.candidates if candidate.ref.slug}
        )
        return _result(
            tool,
            ToolStatus.NO_RESULTS,
            result=base_result,
            diagnostics=(
                _diagnostic(
                    "no_exact_ownership",
                    "No authoritative tier (comfy.org / Manager) claims exact ownership of "
                    f"{node_class!r}; fuzzy search candidates were considered but never "
                    "promoted to a replacement class.",
                    {"considered_packs": considered},
                ),
            ),
        )

    return _result(
        tool,
        ToolStatus.NO_RESULTS,
        result=base_result,
        diagnostics=(
            _diagnostic(
                "no_pack_found",
                f"No pack found for node class {node_class!r} in the attempted registry tiers.",
                {"sources_attempted": list(resolution.source_tiers_attempted)},
            ),
        ),
    )


# ── Node schema lookup ───────────────────────────────────────────────────────

def _default_schema_provider() -> SchemaProvider:
    return get_authoring_schema_provider()


def node_schema(
    node_class: str,
    *,
    provider: SchemaProvider | None = None,
    admission_provider: SchemaProvider | None = None,
) -> ToolResult:
    """Answer whether ``node_class`` is available and what inputs/outputs it can emit.

    ``provider`` defaults to the offline authoring provider (runtime/object_info
    caches, node index, source trees) — deterministic and network-free.  Callers
    may inject any ``SchemaProvider`` (e.g. a live runtime provider).

    RRSYN-5 / RR1-FIX-REV: every hit is labeled against the turn's frozen
    admission snapshot.  Without one (``admission_provider is None``) the
    result is ``admissible: false`` with an explicit
    unknown-to-current-admission note — availability never implies
    admissibility.
    """
    tool = TOOL_NODE_SCHEMA

    if not isinstance(node_class, str) or not node_class.strip():
        return _result(
            tool,
            ToolStatus.INVALID_REQUEST,
            result={"class_type": node_class, "available": False},
            diagnostics=(_diagnostic("empty_node_class", "node_class must be a non-empty class name."),),
        )
    node_class = node_class.strip()

    schema_provider = provider if provider is not None else _default_schema_provider()
    try:
        schema = schema_for(schema_provider, node_class)
    except Exception as exc:  # noqa: BLE001 - provider failures stay typed
        return _result(
            tool,
            ToolStatus.UNAVAILABLE,
            result={"class_type": node_class, "available": False},
            diagnostics=(
                _diagnostic(
                    "schema_provider_unavailable",
                    f"Schema provider failed for {node_class!r}: {type(exc).__name__}: {exc}",
                    {"error_type": type(exc).__name__},
                ),
            ),
        )
    if not isinstance(schema, NodeSchema):
        return _result(
            tool,
            ToolStatus.NO_RESULTS,
            result={
                "class_type": node_class,
                "available": False,
                "is_research_evidence": LOOKUP_IS_RESEARCH_EVIDENCE,
                "evidence_label": "node_schema",
            },
            diagnostics=(
                _diagnostic(
                    "class_not_found",
                    f"Node class {node_class!r} is not available in the local/runtime "
                    "schema providers.",
                    {"class_type": node_class},
                ),
            ),
        )

    inputs: list[dict[str, Any]] = []
    for name in sorted(schema.inputs):
        spec = schema.inputs[name]
        row: dict[str, Any] = {"name": name, "required": bool(spec.required)}
        for field_name in ("type", "default", "choices", "min", "max"):
            value = getattr(spec, field_name, None)
            if value is not None:
                row[field_name] = _json_safe(value)
        inputs.append(row)

    outputs = [
        {
            "type": output.type,
            "name": output.name,
        }
        for output in schema.outputs
        if output is not None
    ]

    provenance: dict[str, Any] = {}
    for field_name in (
        "source_provider",
        "source_path",
        "source_cache_path",
        "source_server_url",
        "source_package",
        "source_version",
        "source_hash",
        "confidence",
    ):
        value = getattr(schema, field_name, None)
        if value is not None:
            provenance[field_name] = _json_safe(value)

    # RR1-FIX-REV (RRSYN-5): fail closed.  A hit is only "admissible" when a
    # frozen admission authority CONFIRMS it; with no admission provider the
    # hit is unknown to current admission — never silently true.
    if admission_provider is None:
        return _result(
            tool,
            ToolStatus.OK,
            result={
                "class_type": schema.class_type,
                "available": True,
                "admissible": False,
                "admission_note": (
                    f"{schema.class_type!r} cannot be checked against any "
                    "frozen admission snapshot: this turn supplied none, so "
                    "the class is unknown to current admission. Edits "
                    "referencing it will be rejected until its owning pack "
                    "capture is loaded into the turn."
                ),
                "pack": schema.pack,
                "stub_schema": bool(is_workflow_stub_schema(schema)),
                "inputs": inputs,
                "input_names": [row["name"] for row in inputs],
                "outputs": outputs,
                "output_count": len(outputs),
                "provenance": provenance,
                "is_research_evidence": LOOKUP_IS_RESEARCH_EVIDENCE,
                "evidence_label": "node_schema",
            },
        )
    try:
        admitted_schema = schema_for(admission_provider, node_class)
        admissible = isinstance(admitted_schema, NodeSchema)
    except Exception:  # noqa: BLE001 - a failing admission probe stays closed
        admissible = False
    admission_note: str | None = None
    if not admissible:
        admission_note = (
            f"{schema.class_type!r} is NOT in the current turn's frozen "
            "admission snapshot; edits referencing it will be rejected "
            "until its owning pack capture is loaded into the turn."
        )

    return _result(
        tool,
        ToolStatus.OK,
        result={
            "class_type": schema.class_type,
            "available": True,
            "admissible": admissible,
            "admission_note": admission_note,
            "pack": schema.pack,
            "stub_schema": bool(is_workflow_stub_schema(schema)),
            "inputs": inputs,
            "input_names": [row["name"] for row in inputs],
            "outputs": outputs,
            "output_count": len(outputs),
            "provenance": provenance,
            "is_research_evidence": LOOKUP_IS_RESEARCH_EVIDENCE,
            "evidence_label": "node_schema",
        },
    )


# ── Ready-template assets (direct-load, NOT research evidence) ───────────────

class _PathEscape(Exception):
    """A resolved template path escaped the allowed template roots."""


def _default_roots(*, include_dynamic: bool) -> tuple[Path, ...]:
    """Allowed ready-template roots: the repo root, plus dynamic roots on request.

    Dynamic roots mirror ``vibecomfy.registry.ready`` (cwd extras dir, the
    user's ``~/.vibecomfy`` dir, plugin-registered roots).  Plugin loading is
    best-effort: any failure degrades to the repo templates only.
    """
    roots: list[Path] = [ready_registry.READY_ROOT]
    if include_dynamic:
        try:
            from vibecomfy.extras import ensure_plugins_loaded, registered_ready_roots

            ensure_plugins_loaded()
            roots.extend(
                [
                    Path.cwd() / "vibecomfy_extras" / "ready_templates",
                    Path.home() / ".vibecomfy" / "ready_templates",
                    *registered_ready_roots(),
                ]
            )
        except Exception:  # noqa: BLE001 - degrade to repo templates only
            pass
    deduped: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        resolved = root.expanduser().resolve()
        if resolved not in seen:
            deduped.append(resolved)
            seen.add(resolved)
    return tuple(deduped)


def _require_inside(path: Path, resolved_roots: Sequence[Path]) -> None:
    for root in resolved_roots:
        try:
            if path.is_relative_to(root):
                return
        except (ValueError, OSError):
            continue
    raise _PathEscape(str(path))


def _resolve_template_path(template_id: str, roots: Sequence[Path]) -> tuple[Path, Path]:
    """Resolve *template_id* to a confined (path, owning root) pair.

    Mirrors the ready-loader's lookup order (``<id>.py``, bare ``<id>``, then a
    single-level ``*/<id>.py`` glob for flat ids) but every hit is resolved and
    verified inside an allowed root, so ``..``/absolute/symlink escapes cannot
    read files outside the template roots.
    """
    discovery = ready_registry.ready_template_discovery(roots=roots)
    record = ready_registry.resolve_ready_template(template_id, discovery)
    resolved_roots = tuple(root.expanduser().resolve() for root in discovery.roots)
    resolved = record.path.resolve()
    _require_inside(resolved, resolved_roots)
    return resolved, record.root


def _validate_template_id(template_id: Any) -> tuple[bool, str | None]:
    """Return (valid, error_code).  ``error_code`` is refused for escapes."""
    if not isinstance(template_id, str) or not template_id.strip():
        return False, "invalid_request"
    text = template_id.strip()
    if "\x00" in text or text.startswith(("/", "~", "\\")):
        return False, "refused"
    segments = re.split(r"[/\\]+", text)
    if any(segment in {"..", "."} for segment in segments if segment):
        return False, "refused"
    return True, None


def _template_rows(roots: Sequence[Path]) -> list[dict[str, Any]]:
    """Inventory rows for every ready-template source under *roots*."""
    discovery = ready_registry.ready_template_discovery(roots=roots)
    return _template_rows_from_discovery(discovery)


def _template_rows_from_discovery(
    discovery: ready_registry.ReadyTemplateDiscovery,
) -> list[dict[str, Any]]:
    """Build inventory rows from an already captured physical snapshot."""
    rows: list[dict[str, Any]] = []
    for record in discovery.records:
        row: dict[str, Any] = {
            "id": record.template_id,
            "path": record.path.relative_to(record.root).as_posix(),
            "scope": record.source_scope,
        }
        aliases = discovery.by_lookup.get(ready_registry._ready_lookup_key(record.template_id), ())
        if len(aliases) > 1:
            row.update(ready_registry._collision_details(record.template_id, aliases))
        rows.append(row)
    return rows


def _ready_discovery(
    *,
    roots: Sequence[Path] | None,
    include_dynamic: bool,
) -> ready_registry.ReadyTemplateDiscovery:
    """Capture the canonical physical snapshot used by one lookup operation."""
    if roots is not None:
        return ready_registry.ready_template_discovery(roots=roots)
    return ready_registry.ready_template_discovery(include_dynamic=include_dynamic)


def _collision_candidates(
    template_id: str,
    discovery: ready_registry.ReadyTemplateDiscovery,
) -> list[ready_registry.ReadyTemplateRecord]:
    query_id = ready_registry._normalize_ready_template_id(template_id)
    if "/" in query_id:
        return list(discovery.by_lookup.get(ready_registry._ready_lookup_key(query_id), ()))
    lookup_key = ready_registry._ready_lookup_key(query_id)
    return [
        record
        for record in discovery.records
        if ready_registry._ready_lookup_key(record.template_id.rsplit("/", 1)[-1]) == lookup_key
    ]


def ready_template_list(
    capability: str | None = None,
    *,
    include_dynamic: bool = False,
    roots: Sequence[Path] | None = None,
) -> ToolResult:
    """List shipping ready-template assets, optionally filtered by capability.

    Capability filtering is a plain token containment check over the template
    id (e.g. ``wan`` matches ``video/wan_t2v``); it is inventory filtering, not
    relevance ranking.  Results are direct assets — explicitly NOT research
    evidence.
    """
    tool = TOOL_READY_TEMPLATE_LIST

    if capability is not None and (not isinstance(capability, str) or not capability.strip()):
        return _result(
            tool,
            ToolStatus.INVALID_REQUEST,
            result={"capability": capability, "is_research_evidence": READY_IS_RESEARCH_EVIDENCE},
            diagnostics=(
                _diagnostic(
                    "invalid_capability",
                    "capability must be a non-empty string or None.",
                    {"capability": capability},
                ),
            ),
        )
    capability = capability.strip() if capability else None

    try:
        discovery = _ready_discovery(roots=roots, include_dynamic=include_dynamic)
        rows = _template_rows_from_discovery(discovery)
    except Exception as exc:  # noqa: BLE001 - lookup transport remains typed
        return _result(
            tool,
            ToolStatus.UNAVAILABLE,
            result={
                "filter": capability,
                "count": 0,
                "templates": [],
                "is_research_evidence": READY_IS_RESEARCH_EVIDENCE,
                "evidence_label": READY_EVIDENCE_LABEL,
            },
            diagnostics=(
                _diagnostic(
                    "ready_discovery_unavailable",
                    f"Ready-template discovery failed: {type(exc).__name__}: {exc}",
                    {"error_type": type(exc).__name__},
                ),
            ),
        )
    if capability is not None:
        rows = [row for row in rows if _capability_matches(capability, row["id"])]

    if not rows:
        return _result(
            tool,
            ToolStatus.NO_RESULTS,
            result={
                "filter": capability,
                "count": 0,
                "templates": [],
                "is_research_evidence": READY_IS_RESEARCH_EVIDENCE,
                "evidence_label": READY_EVIDENCE_LABEL,
            },
            diagnostics=(
                _diagnostic(
                    "no_ready_templates",
                    "No ready templates match the request."
                    if capability
                    else "No ready templates are available.",
                    {"filter": capability},
                ),
            ),
        )

    return _result(
        tool,
        ToolStatus.OK,
        result={
            "filter": capability,
            "count": len(rows),
            "templates": rows,
            "is_research_evidence": READY_IS_RESEARCH_EVIDENCE,
            "evidence_label": READY_EVIDENCE_LABEL,
        },
    )


def _capability_matches(capability: str, template_id: str) -> bool:
    haystack = re.sub(r"[^a-z0-9]+", " ", template_id.lower())
    tokens = re.findall(r"[a-z0-9]+", capability.lower())
    return all(token in haystack for token in tokens)


def ready_template_load(
    template_id: str,
    *,
    include_dynamic: bool = False,
    roots: Sequence[Path] | None = None,
    include_content: bool = True,
) -> ToolResult:
    """Load one ready-template source asset, path-confined.

    Returns the stable template identity (id derived from the confined path),
    a sha256 content hash, size, scope, and the source text (capped).  The
    result is labeled a direct asset — explicitly NOT research evidence — so it
    can never be cited as precedent.

    Path confinement: the id is resolved only under the allowed template roots;
    traversal (``..``, absolute paths, symlink escapes) is refused.
    """
    tool = TOOL_READY_TEMPLATE_LOAD

    valid, error_code = _validate_template_id(template_id)
    if not valid:
        status = ToolStatus.INVALID_REQUEST if error_code == "invalid_request" else ToolStatus.REFUSED
        return _result(
            tool,
            status,
            result={"requested_id": template_id, "is_research_evidence": READY_IS_RESEARCH_EVIDENCE},
            diagnostics=(
                _diagnostic(
                    "template_path_escape_refused" if status is ToolStatus.REFUSED else "invalid_template_id",
                    "Ready-template ids are confined to the template roots; "
                    "path traversal or absolute ids are refused."
                    if status is ToolStatus.REFUSED
                    else "template_id must be a non-empty string.",
                    {"template_id": template_id},
                ),
            ),
        )

    requested_id = template_id
    try:
        discovery = _ready_discovery(roots=roots, include_dynamic=include_dynamic)
    except Exception as exc:  # noqa: BLE001 - lookup transport remains typed
        return _result(
            tool,
            ToolStatus.UNAVAILABLE,
            result={"requested_id": requested_id, "is_research_evidence": READY_IS_RESEARCH_EVIDENCE},
            diagnostics=(
                _diagnostic(
                    "ready_discovery_unavailable",
                    f"Ready-template discovery failed: {type(exc).__name__}: {exc}",
                    {"error_type": type(exc).__name__},
                ),
            ),
        )
    try:
        record = ready_registry.resolve_ready_template(template_id, discovery)
        path = record.path.resolve()
        _require_inside(path, tuple(root.expanduser().resolve() for root in discovery.roots))
        owning_root = record.root
    except ValueError as exc:
        candidates = _collision_candidates(requested_id, discovery)
        return _result(
            tool,
            ToolStatus.REFUSED,
            result={"requested_id": requested_id, "is_research_evidence": READY_IS_RESEARCH_EVIDENCE},
            diagnostics=(
                _diagnostic(
                    "template_alias_ambiguous",
                    str(exc),
                    {
                        "template_id": requested_id,
                        "candidates": [record.template_id for record in candidates],
                        "paths": [str(record.path) for record in candidates],
                    },
                ),
            ),
        )
    except _PathEscape as exc:
        return _result(
            tool,
            ToolStatus.REFUSED,
            result={"requested_id": requested_id, "is_research_evidence": READY_IS_RESEARCH_EVIDENCE},
            diagnostics=(
                _diagnostic(
                    "template_path_escape_refused",
                    "Resolved template path escapes the allowed template roots; refusing to load.",
                    {"resolved_path": str(exc), "template_id": requested_id},
                ),
            ),
        )
    except KeyError:
        return _result(
            tool,
            ToolStatus.NO_RESULTS,
            result={"requested_id": requested_id, "is_research_evidence": READY_IS_RESEARCH_EVIDENCE},
            diagnostics=(
                _diagnostic(
                    "template_not_found",
                    f"Ready template {requested_id!r} not found under the template roots.",
                    {"template_id": requested_id},
                ),
            ),
        )

    try:
        data = path.read_bytes()
    except OSError as exc:
        return _result(
            tool,
            ToolStatus.UNAVAILABLE,
            result={"requested_id": requested_id, "is_research_evidence": READY_IS_RESEARCH_EVIDENCE},
            diagnostics=(
                _diagnostic(
                    "template_unreadable",
                    f"Could not read ready template {requested_id!r}: {type(exc).__name__}: {exc}",
                    {"path": str(path)},
                ),
            ),
        )

    stable_id = record.template_id
    relative_path = record.path.relative_to(owning_root).as_posix()
    content: str | None = None
    truncated = False
    if include_content:
        content = data.decode("utf-8", errors="replace")
        if len(content) > READY_CONTENT_CHAR_CAP:
            content = content[:READY_CONTENT_CHAR_CAP]
            truncated = True

    return _result(
        tool,
        ToolStatus.OK,
        result={
            "id": stable_id,
            "requested_id": requested_id,
            "path": relative_path,
            "scope": record.source_scope,
            "sha256": hashlib.sha256(data).hexdigest(),
            "size_bytes": len(data),
            "content": content,
            "content_truncated": truncated,
            "is_research_evidence": READY_IS_RESEARCH_EVIDENCE,
            "evidence_label": READY_EVIDENCE_LABEL,
        },
    )


# ── Tool registry (implement-phase + research-phase tool surface) ────────────

LOOKUP_TOOLS: Mapping[str, Callable[..., ToolResult]] = {
    TOOL_REGISTRY_LOOKUP: registry_lookup,
    TOOL_NODE_SCHEMA: node_schema,
    TOOL_READY_TEMPLATE_LIST: ready_template_list,
    TOOL_READY_TEMPLATE_LOAD: ready_template_load,
}

__all__ = [
    "EXACT_OWNERSHIP_SOURCES",
    "LOOKUP_IS_RESEARCH_EVIDENCE",
    "LOOKUP_TOOLS",
    "READY_CONTENT_CHAR_CAP",
    "READY_EVIDENCE_LABEL",
    "READY_IS_RESEARCH_EVIDENCE",
    "REGISTRY_LOOKUP_BUDGET_PER_STAGE",
    "RegistryLookupBudget",
    "TOOL_NODE_SCHEMA",
    "TOOL_READY_TEMPLATE_LIST",
    "TOOL_READY_TEMPLATE_LOAD",
    "TOOL_REGISTRY_LOOKUP",
    "node_schema",
    "ready_template_list",
    "ready_template_load",
    "registry_lookup",
]
