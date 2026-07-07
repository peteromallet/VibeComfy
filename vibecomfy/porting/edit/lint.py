"""Pure lint data model and read-only index for agent-edit delta hygiene.

Provides :class:`LintIssue`, :class:`LintResult`, :class:`LintNormalization`
and the immutable :class:`LintIndex` that maps a raw LiteGraph UI dict into
deterministic canonical-uid and LiteGraph-id lookups with no side effects.

Design
------
- ``LintIndex`` is built from ``original_ui`` via ``EditLedger.ingest()``.
- Canonical uids (stamped by the ledger) and raw LiteGraph integer ids are
  indexed separately so later lint rules can resolve either reference form.
- Node metadata (class_type, input/output names, slot indices) is extracted
  once and exposed read-only.
- Link indexing covers both link-id and endpoint-based lookups.
- All dataclasses are frozen; the index is never mutated after construction.

``lint_delta()``
----------------
The main entry point accepts a sequence of :class:`EditOp` objects and a
:class:`LintIndex`, and returns a :class:`LintResult` with:

- **surviving** ops (possibly with LiteGraph ids rewritten to canonical uids)
- **issues** (typed errors for unknown targets / fields / malformed ops)
- **normalizations** (disposition of every original op)

Rules enforced:

- *identity* – LiteGraph integer ids in uid positions are normalised to the
  canonical uid.  Ops whose target node exists pass through with the uid
  rewritten if needed.
- *unknown target* – any node, link, or field reference that cannot be
  resolved produces a ``rejected`` disposition with a typed issue.
- *field no-op* – ``set_node_field`` ops that would set a field to its
  current value are dropped as ``dropped_noop``.
- *mode no-op* – ``set_mode`` ops that set the mode the node already has
  are dropped as ``dropped_noop``.
- *add_node* – validates that ``class_type`` is non-empty and (when a
  ``schema_provider`` is supplied) that the class is known and all
  ``inputs`` keys name valid inputs on that class.
- *upsert_link* – resolves source/target uids, validates output slots
  and input fields exist, and detects no-ops when an identical link
  already exists.  Socket-type compatibility is deferred to apply.
- *remove_link* – validates link-id or target-based references and
  detects no-ops when no matching link is found.  Does not dereference
  link ids across scopes (link-id searches are root-scope only).
- *reorder* – validates axis and that the target node exists; ``order``
  content is not validated against current widget/slot names.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Mapping, Sequence

from .ledger import EditLedger
from .ops import (
    AddNodeOp,
    EditOp,
    LinkSourceRef,
    LinkTargetRef,
    NodeFieldTarget,
    NodeTarget,
    RemoveLinkOp,
    RemoveNodeOp,
    ReorderOp,
    SetModeOp,
    SetNodeFieldOp,
    UpsertLinkOp,
)
from vibecomfy.porting.resolution import (
    _NodeMeta,
    LintIndexBackend,
    ResolutionContext,
    ResolutionIssue,
    build_lg_id_maps,
)
from vibecomfy.porting.edit._ir_utils import _canonical_input_name_for_class


_IMAGE_CONCAT_MULTI_INPUT_RE = re.compile(r"^image_(\d+)$")


def _is_dynamic_add_node_input(
    *,
    class_type: str,
    input_name: str,
    fields: Mapping[str, Any],
    schema_inputs: Mapping[str, Any],
) -> bool:
    if class_type != "ImageConcatMulti":
        return False
    match = _IMAGE_CONCAT_MULTI_INPUT_RE.match(input_name)
    if match is None:
        return False
    try:
        index = int(match.group(1))
    except ValueError:
        return False
    if index < 1:
        return False

    raw_count = fields.get("inputcount")
    if raw_count is None:
        inputcount_spec = schema_inputs.get("inputcount")
        raw_count = getattr(inputcount_spec, "default", None)
    try:
        count = int(raw_count)
    except (TypeError, ValueError):
        return False
    return index <= count


# ── data model ──────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class LintIssue:
    """One lint finding for an edit operation.

    Analogous to ``PortIssue`` but scoped to delta-level concerns:
    no-op detection, identity resolution, structural malformation, etc.
    """

    code: str
    message: str
    severity: str = "error"  # "error", "warning", "info"
    op_index: int | None = None  # position in the original delta
    op_kind: str | None = None  # e.g. "add_node", "set_node_field"
    scope_path: str | None = None
    uid: str | None = None
    lg_id: int | None = None
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LintNormalization:
    """Describes what happened to a single edit op during linting."""

    op_index: int
    op: EditOp
    disposition: str  # "passed", "dropped_noop", "rejected"
    issue: LintIssue | None = None  # set when disposition is not "passed"


@dataclass(frozen=True, slots=True)
class LintResult:
    """The outcome of linting a delta against a :class:`LintIndex`.

    ``surviving`` contains only the ops that passed lint (no-ops are dropped,
    malformed ops are rejected).  ``normalizations`` records the disposition
    of every op in the original delta so callers can emit diagnostics or adjust
    landed-count accounting.
    """

    surviving: tuple[EditOp, ...]
    issues: tuple[LintIssue, ...]
    normalizations: tuple[LintNormalization, ...]

    @property
    def passed_count(self) -> int:
        return sum(
            1 for n in self.normalizations if n.disposition == "passed"
        )

    @property
    def dropped_count(self) -> int:
        return sum(
            1 for n in self.normalizations if n.disposition == "dropped_noop"
        )

    @property
    def rejected_count(self) -> int:
        return sum(
            1 for n in self.normalizations if n.disposition == "rejected"
        )


# ── LintIndex ───────────────────────────────────────────────────────────────

def _build_node_meta(
    ledger: EditLedger,
) -> dict[tuple[str, str], _NodeMeta]:
    """Extract node metadata from every scoped node in *ledger*."""
    meta: dict[tuple[str, str], _NodeMeta] = {}
    for (scope_path, uid), node in ledger.node_index.items():
        lg_id: int | None = node.get("id")
        if not isinstance(lg_id, int):
            # defensive: every LiteGraph node MUST have an integer id
            lg_id = -1
        class_type: str = node.get("type") or node.get("class_type") or ""
        # input names in insertion order (LiteGraph preserves it)
        raw_inputs = node.get("inputs")
        input_names: tuple[str, ...] = ()
        if isinstance(raw_inputs, list):
            input_names = tuple(
                entry.get("name") or ""
                for entry in raw_inputs
                if isinstance(entry, dict)
            )
        # output names + slot indices
        raw_outputs = node.get("outputs")
        output_names: tuple[str, ...] = ()
        output_slots: dict[str, int] = {}
        if isinstance(raw_outputs, list):
            out_names: list[str] = []
            for entry in raw_outputs:
                if isinstance(entry, dict):
                    name = entry.get("name") or ""
                    out_names.append(name)
                    slot = entry.get("slot_index")
                    if isinstance(slot, int):
                        output_slots[name] = slot
            output_names = tuple(out_names)
        meta[(scope_path, uid)] = _NodeMeta(
            scope_path=scope_path,
            uid=uid,
            lg_id=lg_id,
            class_type=class_type,
            input_names=input_names,
            output_names=output_names,
            output_slots=output_slots,
        )
    return meta


def _build_link_sets(
    ledger: EditLedger,
) -> tuple[
    dict[str, frozenset[int]],
    dict[tuple[str, int], Any],
]:
    """Collect existing link ids per scope and a link-by-id lookup."""
    link_ids: dict[str, set[int]] = {}
    link_by_id: dict[tuple[str, int], Any] = {}
    for (scope_path, link_id), link in ledger.link_index.items():
        link_ids.setdefault(scope_path, set()).add(link_id)
        link_by_id[(scope_path, link_id)] = link
    frozen: dict[str, frozenset[int]] = {
        sp: frozenset(ids) for sp, ids in link_ids.items()
    }
    return frozen, link_by_id


@dataclass(frozen=True, slots=True)
class LintIndex:
    """Read-only index over an ``original_ui`` LiteGraph dict.

    Built deterministically from ``original_ui`` via ``EditLedger.ingest()``.
    Exposes canonical-uid and LiteGraph-id lookups, node metadata, and
    existing link indexing for downstream lint rules.

    Usage::

        index = LintIndex.build(original_ui)

        # resolve a node by canonical uid or LiteGraph id
        index.node_by_uid(scope_path, uid)
        index.node_by_lg_id(scope_path, lg_id)

        # translate between uid and LiteGraph id
        index.uid_for_lg_id(scope_path, lg_id)
        index.lg_id_for_uid(scope_path, uid)

        # inspect node metadata
        meta = index.node_meta_for(scope_path, uid)
        meta.class_type
        meta.input_names
        meta.output_names
    """

    ledger: EditLedger = field(repr=False)
    # LiteGraph integer id → canonical uid (per scope)
    _lg_id_to_uid: dict[tuple[str, int], str] = field(repr=False)
    # canonical uid → LiteGraph integer id (per scope)
    _uid_to_lg_id: dict[tuple[str, str], int] = field(repr=False)
    # (scope_path, uid) → immutable node metadata
    _node_meta: dict[tuple[str, str], _NodeMeta] = field(repr=False)
    # scope_path → frozen set of existing link ids
    _link_ids: dict[str, frozenset[int]] = field(repr=False)
    # (scope_path, link_id) → raw link object
    _link_by_id: dict[tuple[str, int], Any] = field(repr=False)

    @classmethod
    def build(cls, original_ui: Mapping[str, Any]) -> "LintIndex":
        """Construct a read-only index from a raw LiteGraph UI dict.

        *original_ui* is a LiteGraph serialisation dict (nodes, links,
        definitions, etc.) as stored in the workflow JSON.
        """
        ledger = EditLedger.ingest(original_ui)
        lg_id_to_uid, uid_to_lg_id = build_lg_id_maps(ledger.node_index)
        node_meta = _build_node_meta(ledger)
        link_ids, link_by_id = _build_link_sets(ledger)
        return cls(
            ledger=ledger,
            _lg_id_to_uid=lg_id_to_uid,
            _uid_to_lg_id=uid_to_lg_id,
            _node_meta=node_meta,
            _link_ids=link_ids,
            _link_by_id=link_by_id,
        )

    # -- scope helpers --------------------------------------------------------

    @property
    def scope_paths(self) -> tuple[str, ...]:
        """All scope paths in insertion order (root ``""`` first)."""
        return tuple(self.ledger.scopes.keys())

    def has_scope(self, scope_path: str) -> bool:
        return scope_path in self.ledger.scopes

    # -- node resolution ------------------------------------------------------

    def node_by_uid(
        self, scope_path: str, uid: str
    ) -> dict[str, Any] | None:
        """Return the LiteGraph node dict for *uid* in *scope_path*."""
        return self.ledger.resolve_node(scope_path, uid)

    def node_by_lg_id(
        self, scope_path: str, lg_id: int
    ) -> dict[str, Any] | None:
        """Return the LiteGraph node dict for *lg_id* in *scope_path*."""
        uid = self._lg_id_to_uid.get((scope_path, lg_id))
        if uid is None:
            return None
        return self.ledger.resolve_node(scope_path, uid)

    # -- uid ↔ lg_id translation ----------------------------------------------

    def uid_for_lg_id(self, scope_path: str, lg_id: int) -> str | None:
        """Return the canonical uid for *lg_id* in *scope_path*."""
        return self._lg_id_to_uid.get((scope_path, lg_id))

    def lg_id_for_uid(self, scope_path: str, uid: str) -> int | None:
        """Return the LiteGraph integer id for *uid* in *scope_path*."""
        return self._uid_to_lg_id.get((scope_path, uid))

    # -- node existence and metadata ------------------------------------------

    def node_exists(self, scope_path: str, uid: str) -> bool:
        """Return True if *uid* names a node in *scope_path*."""
        return (scope_path, uid) in self._node_meta

    def node_meta_for(
        self, scope_path: str, uid: str
    ) -> _NodeMeta | None:
        """Return immutable metadata for *uid* in *scope_path*."""
        return self._node_meta.get((scope_path, uid))

    def class_type_for(self, scope_path: str, uid: str) -> str | None:
        """Return the ``class_type`` for *uid* in *scope_path*."""
        meta = self._node_meta.get((scope_path, uid))
        return meta.class_type if meta is not None else None

    def input_names_for(self, scope_path: str, uid: str) -> tuple[str, ...]:
        """Return input names for *uid* in *scope_path* (empty if unknown)."""
        meta = self._node_meta.get((scope_path, uid))
        return meta.input_names if meta is not None else ()

    def output_names_for(self, scope_path: str, uid: str) -> tuple[str, ...]:
        """Return output names for *uid* in *scope_path* (empty if unknown)."""
        meta = self._node_meta.get((scope_path, uid))
        return meta.output_names if meta is not None else ()

    def output_slot_for(
        self, scope_path: str, uid: str, output_name: str
    ) -> int | None:
        """Return the LiteGraph slot_index for *output_name* (or None)."""
        meta = self._node_meta.get((scope_path, uid))
        if meta is None:
            return None
        return meta.output_slots.get(output_name)

    # -- link indexing --------------------------------------------------------

    def link_ids_for_scope(self, scope_path: str) -> frozenset[int]:
        """Return the frozen set of existing link ids in *scope_path*."""
        return self._link_ids.get(scope_path, frozenset())

    def link_by_id(
        self, scope_path: str, link_id: int
    ) -> Any | None:
        """Return the raw link object for *link_id* in *scope_path*."""
        return self._link_by_id.get((scope_path, link_id))

    def link_exists(self, scope_path: str, link_id: int) -> bool:
        """Return True if *link_id* exists in *scope_path*."""
        return (scope_path, link_id) in self._link_by_id


# ── lint helpers ────────────────────────────────────────────────────────────

def _node_label(index: LintIndex, scope_path: str, uid: str) -> str:
    """Return a human-readable label for *uid* in *scope_path*.

    Uses ``class_type`` as the primary label; appends ``title`` when it
    is non-empty and differs from the class type (e.g.
    ``"CLIPTextEncode 'my prompt'"``).  Falls back to the raw *uid* when
    no metadata is available.
    """
    meta = index.node_meta_for(scope_path, uid)
    if meta is None:
        return uid
    class_type = meta.class_type or "node"
    node = index.node_by_uid(scope_path, uid)
    title: str | None = None
    if isinstance(node, dict):
        raw_title = node.get("title")
        if isinstance(raw_title, str) and raw_title.strip():
            title = raw_title.strip()
    if title and title != class_type:
        return f"{class_type} '{title}'"
    return class_type


def _display_value(value: object, *, limit: int = 48) -> str:
    """Render *value* as a compact, human-readable string (no raw dicts)."""
    if isinstance(value, str):
        text = value
    elif value is None:
        text = "null"
    elif isinstance(value, (int, float, bool)):
        text = str(value)
    else:
        import json as _json

        try:
            text = _json.dumps(_json_safe(value), sort_keys=True)
        except (TypeError, ValueError):
            text = str(value)
    # Collapse whitespace
    text = " ".join(text.split())
    if len(text) > limit:
        return text[: max(0, limit - 1)] + "…"
    return text


def _json_safe(obj: object) -> object:
    """Coerce *obj* to a JSON-serialisable value."""
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    return str(obj)


def _make_issue(
    code: str,
    message: str,
    *,
    severity: str = "error",
    op_index: int | None = None,
    op_kind: str | None = None,
    scope_path: str | None = None,
    uid: str | None = None,
    lg_id: int | None = None,
    detail: dict[str, Any] | None = None,
) -> LintIssue:
    return LintIssue(
        code=code,
        message=message,
        severity=severity,
        op_index=op_index,
        op_kind=op_kind,
        scope_path=scope_path,
        uid=uid,
        lg_id=lg_id,
        detail=dict(detail or {}),
    )


_ctx = ResolutionContext()


def _ri_to_lint_issue(
    ri: ResolutionIssue,
    *,
    op_index: int,
    op_kind: str,
) -> LintIssue:
    """Adapt a ResolutionIssue from ResolutionContext to a LintIssue."""
    lg_id: int | None = ri.detail.get("lg_id") if ri.detail else None
    if not isinstance(lg_id, int):
        lg_id = None
    return LintIssue(
        code=ri.code,
        message=ri.message,
        severity=ri.severity,
        op_index=op_index,
        op_kind=op_kind,
        scope_path=ri.scope_path,
        uid=ri.uid,
        lg_id=lg_id,
        detail=ri.detail,
    )


def _resolve_uid(
    index: LintIndex,
    scope_path: str,
    uid_str: str,
    *,
    op_index: int,
    op_kind: str,
) -> tuple[str | None, LintIssue | None]:
    result = _ctx.resolve_uid(LintIndexBackend(index), scope_path, uid_str)
    if result.value is not None:
        return result.value, None
    issue = _ri_to_lint_issue(result.issues[0], op_index=op_index, op_kind=op_kind) if result.issues else None
    return None, issue


def _resolve_node_target(
    index: LintIndex,
    target: NodeTarget,
    *,
    op_index: int,
    op_kind: str,
) -> tuple[NodeTarget | None, LintIssue | None]:
    result = _ctx.resolve_node_target(LintIndexBackend(index), target)
    if result.value is not None:
        return result.value, None
    issue = _ri_to_lint_issue(result.issues[0], op_index=op_index, op_kind=op_kind) if result.issues else None
    return None, issue


def _resolve_node_field_target(
    index: LintIndex,
    target: NodeFieldTarget,
    *,
    op_index: int,
    op_kind: str,
) -> tuple[NodeFieldTarget | None, LintIssue | None]:
    result = _ctx.resolve_node_field_target(LintIndexBackend(index), target)
    if result.value is not None:
        return result.value, None
    issue = _ri_to_lint_issue(result.issues[0], op_index=op_index, op_kind=op_kind) if result.issues else None
    return None, issue


def _resolve_link_source(
    index: LintIndex,
    source: LinkSourceRef,
    *,
    op_index: int,
    op_kind: str,
) -> tuple[LinkSourceRef | None, LintIssue | None]:
    result = _ctx.resolve_link_source(LintIndexBackend(index), source)
    if result.value is not None:
        return result.value, None
    issue = _ri_to_lint_issue(result.issues[0], op_index=op_index, op_kind=op_kind) if result.issues else None
    return None, issue


def _resolve_link_target(
    index: LintIndex,
    target: LinkTargetRef,
    *,
    op_index: int,
    op_kind: str,
) -> tuple[LinkTargetRef | None, LintIssue | None]:
    result = _ctx.resolve_link_target(LintIndexBackend(index), target)
    if result.value is not None:
        return result.value, None
    issue = _ri_to_lint_issue(result.issues[0], op_index=op_index, op_kind=op_kind) if result.issues else None
    return None, issue


def _link_origin_id(link: Any) -> int | None:
    """Extract the origin node LiteGraph id from a raw link object."""
    if isinstance(link, Mapping):
        oid = link.get("origin_id")
        if isinstance(oid, int):
            return oid
        return None
    if isinstance(link, (list, tuple)) and len(link) >= 2:
        oid = link[1]
        if isinstance(oid, int):
            return oid
    return None


def _link_origin_slot(link: Any) -> int | None:
    """Extract the origin slot index from a raw link object."""
    if isinstance(link, Mapping):
        slot = link.get("origin_slot")
        if isinstance(slot, int):
            return slot
        return None
    if isinstance(link, (list, tuple)) and len(link) >= 3:
        slot = link[2]
        if isinstance(slot, int):
            return slot
    return None


def _link_target_id(link: Any) -> int | None:
    """Extract the target node LiteGraph id from a raw link object."""
    if isinstance(link, Mapping):
        tid = link.get("target_id")
        if isinstance(tid, int):
            return tid
        return None
    if isinstance(link, (list, tuple)) and len(link) >= 4:
        tid = link[3]
        if isinstance(tid, int):
            return tid
    return None


def _link_target_slot(link: Any) -> int | None:
    """Extract the target slot index from a raw link object."""
    if isinstance(link, Mapping):
        slot = link.get("target_slot")
        if isinstance(slot, int):
            return slot
        return None
    if isinstance(link, (list, tuple)) and len(link) >= 5:
        slot = link[4]
        if isinstance(slot, int):
            return slot
    return None


def _resolve_output_slot_index(
    index: LintIndex, scope_path: str, uid: str, output_slot: str | int,
    *, schema_provider: Any = None,
) -> int | None:
    result = _ctx.resolve_output_slot_index(
        LintIndexBackend(index),
        scope_path,
        uid,
        output_slot,
        schema_provider=schema_provider,
    )
    return result.value


def _resolve_input_slot_index(
    index: LintIndex, scope_path: str, uid: str, input_field: str,
) -> int | None:
    result = _ctx.resolve_input_slot_index(LintIndexBackend(index), scope_path, uid, input_field)
    return result.value


def _find_matching_link(
    index: LintIndex,
    scope_path: str,
    source_uid: str,
    output_slot: str | int,
    target_uid: str,
    input_field: str,
) -> Any | None:
    """Return the first existing link that matches the given endpoints.

    Returns the raw link object if found, or ``None``.
    """
    source_lg_id = index.lg_id_for_uid(scope_path, source_uid)
    target_lg_id = index.lg_id_for_uid(scope_path, target_uid)
    if source_lg_id is None or target_lg_id is None:
        return None

    source_slot_idx = _resolve_output_slot_index(
        index, scope_path, source_uid, output_slot,
    )
    target_slot_idx = _resolve_input_slot_index(
        index, scope_path, target_uid, input_field,
    )
    if source_slot_idx is None or target_slot_idx is None:
        return None

    for link_id in index.link_ids_for_scope(scope_path):
        link = index.link_by_id(scope_path, link_id)
        if link is None:
            continue
        oid = _link_origin_id(link)
        osl = _link_origin_slot(link)
        tid = _link_target_id(link)
        tsl = _link_target_slot(link)
        if (oid == source_lg_id and osl == source_slot_idx
                and tid == target_lg_id and tsl == target_slot_idx):
            return link
    return None


def _node_field_value(
    index: LintIndex, scope_path: str, uid: str, field_path: str
) -> Any:
    """Read the current value of *field_path* from the live node dict.

    Returns a sentinel (``_MISSING``) when the field does not exist.
    """
    node = index.node_by_uid(scope_path, uid)
    if node is None:
        return _MISSING
    # Widget values are stored as a list; field_path is like "widgets.0"
    if field_path.startswith("widgets."):
        try:
            idx = int(field_path.split(".", 1)[1])
        except (ValueError, IndexError):
            return _MISSING
        widgets = node.get("widgets_values")
        if isinstance(widgets, list) and 0 <= idx < len(widgets):
            return widgets[idx]
        return _MISSING
    # Top-level node property
    if field_path in node:
        return node[field_path]
    # Nested property access via dotted path (e.g. "properties.some_key")
    parts = field_path.split(".")
    current: Any = node
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part, _MISSING)
        else:
            return _MISSING
    return current


class _MissingSentinel:
    """Unique sentinel for absent field lookups."""

    def __repr__(self) -> str:
        return "<MISSING>"


_MISSING = _MissingSentinel()


# ── per-op linters ──────────────────────────────────────────────────────────

def _lint_set_node_field(
    op: SetNodeFieldOp, op_index: int, index: LintIndex
) -> tuple[EditOp | None, LintIssue | None, str]:
    """Lint a ``set_node_field`` op.

    Returns ``(normalized_op | None, issue | None, disposition)``.
    """
    target, issue = _resolve_node_field_target(
        index, op.target, op_index=op_index, op_kind="set_node_field",
    )
    if target is None:
        return None, issue, "rejected"

    # Check that the field exists on the node
    current = _node_field_value(index, target.scope_path, target.uid, target.field_path)
    if current is _MISSING:
        # When a node carries widget values the field path may name a widget
        # whose index we cannot resolve without schema assistance.  Rather
        # than rejecting outright we pass through with a warning so that
        # apply_delta (which has full widget-name resolution) makes the
        # final decision.  Nodes with no widget surface at all still
        # hard-reject genuinely unknown fields.
        node = index.node_by_uid(target.scope_path, target.uid)
        widgets_values = node.get("widgets_values") if isinstance(node, dict) else None
        has_widget_surface = (
            isinstance(widgets_values, (list, dict))
            and len(widgets_values) > 0
        )
        # Only pass through unqualified names that might be widget names;
        # explicit widget-index paths (widgets.N) that are out of range
        # still hard-reject.
        if has_widget_surface and not target.field_path.startswith("widgets."):
            return op, _make_issue(
                "unknown_field",
                f"{_node_label(index, target.scope_path, target.uid)} field "
                f"'{target.field_path}' was not resolved; the node has "
                f"widget values so this may be a widget-name reference — "
                f"passing through for apply_delta validation.",
                severity="warning",
                op_index=op_index,
                op_kind="set_node_field",
                scope_path=target.scope_path,
                uid=target.uid,
                detail={"field_path": target.field_path},
            ), "passed"
        return None, _make_issue(
            "unknown_field",
            f"{_node_label(index, target.scope_path, target.uid)} has no "
            f"field '{target.field_path}'.",
            op_index=op_index,
            op_kind="set_node_field",
            scope_path=target.scope_path,
            uid=target.uid,
            detail={"field_path": target.field_path},
        ), "rejected"

    # No-op detection: value unchanged
    if current == op.value:
        return None, _make_issue(
            "noop_field",
            f"{_node_label(index, target.scope_path, target.uid)} "
            f"{target.field_path} is already {_display_value(op.value)}.",
            severity="info",
            op_index=op_index,
            op_kind="set_node_field",
            scope_path=target.scope_path,
            uid=target.uid,
            detail={"field_path": target.field_path, "current": current, "requested": op.value},
        ), "dropped_noop"

    # Pass through (possibly with rewritten uid)
    if target is op.target:
        return op, None, "passed"
    return SetNodeFieldOp(op="set_node_field", target=target, value=op.value), None, "passed"


def _lint_add_node(
    op: AddNodeOp,
    op_index: int,
    index: LintIndex,
    schema_provider: Any = None,
) -> tuple[EditOp | None, LintIssue | None, str]:
    """Lint an ``add_node`` op.

    Validates that ``class_type`` is non-empty and (when *schema_provider*
    is available) that the class is a known node type and all ``inputs``
    keys name valid inputs on that class.  Existence checks (duplicate
    uids, etc.) are deferred to apply.
    """
    if not op.class_type.strip():
        return None, _make_issue(
            "empty_class_type",
            "Cannot add a node with an empty class type.",
            op_index=op_index,
            op_kind="add_node",
            scope_path=op.scope_path,
        ), "rejected"

    # Validate that the scope_path exists (empty string = root scope, always valid)
    if op.scope_path and not index.has_scope(op.scope_path):
        return None, _make_issue(
            "unknown_scope",
            f"Scope '{op.scope_path}' does not exist.",
            op_index=op_index,
            op_kind="add_node",
            scope_path=op.scope_path,
        ), "rejected"

    # Schema-aware validation (only when a provider is supplied)
    if schema_provider is not None:
        from vibecomfy.schema import is_workflow_stub_schema, schema_for as _schema_for

        schema = _schema_for(schema_provider, op.class_type.strip())
        if schema is None or is_workflow_stub_schema(schema):
            return None, _make_issue(
                "unknown_class_type",
                f"'{op.class_type.strip()}' is not a known node class.",
                op_index=op_index,
                op_kind="add_node",
                scope_path=op.scope_path,
                detail={"class_type": op.class_type.strip()},
            ), "rejected"

        # Validate input names when inputs are provided
        canonical_fields = dict(op.fields)
        canonical_inputs = dict(op.inputs)
        try:
            schema_inputs: dict[str, Any] = getattr(schema, "inputs", {}) or {}
        except Exception:
            schema_inputs = {}
        if schema_inputs:
            canonical_fields = {
                _canonical_input_name_for_class(schema_inputs, op.class_type.strip(), str(name)): value
                for name, value in op.fields.items()
            }
            canonical_inputs = {
                _canonical_input_name_for_class(schema_inputs, op.class_type.strip(), str(name)): value
                for name, value in op.inputs.items()
            }
            if canonical_fields != dict(op.fields) or canonical_inputs != dict(op.inputs):
                op = AddNodeOp(
                    op=op.op,
                    scope_path=op.scope_path,
                    class_type=op.class_type,
                    fields=canonical_fields,
                    inputs=canonical_inputs,
                    anchor=op.anchor,
                    uid=op.uid,
                    node_id=op.node_id,
                )

        if op.inputs:
            for input_name in op.inputs:
                if input_name not in schema_inputs and not _is_dynamic_add_node_input(
                    class_type=op.class_type.strip(),
                    input_name=input_name,
                    fields=op.fields,
                    schema_inputs=schema_inputs,
                ):
                    return None, _make_issue(
                        "invalid_add_node_input",
                        f"'{input_name}' is not a valid input for "
                        f"'{op.class_type.strip()}'.",
                        op_index=op_index,
                        op_kind="add_node",
                        scope_path=op.scope_path,
                        detail={
                            "class_type": op.class_type.strip(),
                            "invalid_input": input_name,
                            "available_inputs": sorted(schema_inputs.keys()),
                        },
                    ), "rejected"

    return op, None, "passed"


def _lint_remove_node(
    op: RemoveNodeOp, op_index: int, index: LintIndex
) -> tuple[EditOp | None, LintIssue | None, str]:
    """Lint a ``remove_node`` op."""
    target, issue = _resolve_node_target(
        index, op.target, op_index=op_index, op_kind="remove_node",
    )
    if target is None:
        return None, issue, "rejected"

    if target is op.target:
        return op, None, "passed"
    return RemoveNodeOp(op="remove_node", target=target), None, "passed"


def _lint_upsert_link(
    op: UpsertLinkOp,
    op_index: int,
    index: LintIndex,
    schema_provider: Any = None,
) -> tuple[EditOp | None, LintIssue | None, str]:
    """Lint an ``upsert_link`` op.

    Resolves source/target uids, validates endpoint slots exist,
    and detects no-ops when an identical link already exists.
    Socket-type compatibility is deferred to apply.
    """
    source, src_issue = _resolve_link_source(
        index, op.source, op_index=op_index, op_kind="upsert_link",
    )
    if source is None:
        return None, src_issue, "rejected"

    target, tgt_issue = _resolve_link_target(
        index, op.target, op_index=op_index, op_kind="upsert_link",
    )
    if target is None:
        return None, tgt_issue, "rejected"

    # Validate source output slot exists
    output_slot_idx = _resolve_output_slot_index(
        index,
        source.scope_path,
        source.uid,
        source.output_slot,
        schema_provider=schema_provider,
    )
    if output_slot_idx is None:
        return None, _make_issue(
            "bad_output_slot",
            f"{_node_label(index, source.scope_path, source.uid)} has no "
            f"output slot '{source.output_slot}'.",
            op_index=op_index,
            op_kind="upsert_link",
            scope_path=source.scope_path,
            uid=source.uid,
            detail={"output_slot": source.output_slot},
        ), "rejected"

    # Validate target input field exists
    input_slot_idx = _resolve_input_slot_index(
        index, target.scope_path, target.uid, target.input_field,
    )
    if input_slot_idx is None:
        return None, _make_issue(
            "missing_target_input",
            f"{_node_label(index, target.scope_path, target.uid)} has no "
            f"input '{target.input_field}'.",
            op_index=op_index,
            op_kind="upsert_link",
            scope_path=target.scope_path,
            uid=target.uid,
            detail={"input_field": target.input_field},
        ), "rejected"

    # No-op detection: link already exists with same endpoints
    existing = _find_matching_link(
        index,
        source.scope_path,
        source.uid,
        source.output_slot,
        target.uid,
        target.input_field,
    )
    if existing is not None:
        existing_id: int | None = None
        if isinstance(existing, Mapping):
            existing_id = existing.get("id")
        elif isinstance(existing, (list, tuple)) and existing:
            existing_id = existing[0] if isinstance(existing[0], int) else None
        return None, _make_issue(
            "noop_link",
            f"A link from {_node_label(index, source.scope_path, source.uid)} "
            f"to {_node_label(index, target.scope_path, target.uid)} "
            f"({target.input_field}) already exists.",
            severity="info",
            op_index=op_index,
            op_kind="upsert_link",
            scope_path=source.scope_path,
            detail={
                "existing_link_id": existing_id,
                "source_uid": source.uid,
                "source_slot": source.output_slot,
                "target_uid": target.uid,
                "target_field": target.input_field,
            },
        ), "dropped_noop"

    if source is op.source and target is op.target:
        return op, None, "passed"
    return UpsertLinkOp(op="upsert_link", source=source, target=target), None, "passed"


def _lint_remove_link(
    op: RemoveLinkOp,
    op_index: int,
    index: LintIndex,
    schema_provider: Any = None,
) -> tuple[EditOp | None, LintIssue | None, str]:
    """Lint a ``remove_link`` op.

    - ``link_id``-based: rejects if the link does not exist.
    - target-based: rejects unknown nodes; detects no-op when no link matches
      the target endpoint.
    """
    if op.link_id is not None:
        # link_id-based removal: validate link exists
        scope_path = ""  # link_id searches default to root scope
        if not index.link_exists(scope_path, op.link_id):
            return None, _make_issue(
                "unknown_link",
                f"Link id {op.link_id} does not exist.",
                op_index=op_index,
                op_kind="remove_link",
                scope_path=scope_path,
                detail={"link_id": op.link_id},
            ), "rejected"
        return op, None, "passed"

    if op.target is not None:
        # target-based removal: resolve uid and check if a matching link exists
        target, issue = _resolve_link_target(
            index, op.target, op_index=op_index, op_kind="remove_link",
        )
        if target is None:
            return None, issue, "rejected"

        # Look for any link that matches the target endpoint
        target_lg_id = index.lg_id_for_uid(target.scope_path, target.uid)
        target_slot_idx = _resolve_input_slot_index(
            index, target.scope_path, target.uid, target.input_field,
        )
        link_found = False
        if target_lg_id is not None and target_slot_idx is not None:
            for link_id in index.link_ids_for_scope(target.scope_path):
                link = index.link_by_id(target.scope_path, link_id)
                if link is None:
                    continue
                tid = _link_target_id(link)
                tsl = _link_target_slot(link)
                if tid == target_lg_id and tsl == target_slot_idx:
                    link_found = True
                    break

        if not link_found:
            return None, _make_issue(
                "noop_remove_link",
                f"No link targets {_node_label(index, target.scope_path, target.uid)} "
                f"input '{target.input_field}'.",
                severity="info",
                op_index=op_index,
                op_kind="remove_link",
                scope_path=target.scope_path,
                uid=target.uid,
                detail={"input_field": target.input_field},
            ), "dropped_noop"

        if target is op.target:
            return op, None, "passed"
        return RemoveLinkOp(op="remove_link", link_id=None, target=target), None, "passed"

    # Should not happen (parse_edit_op enforces this)
    return None, _make_issue(
        "malformed_op",
        "A remove_link operation must specify either an id or a target.",
        op_index=op_index,
        op_kind="remove_link",
    ), "rejected"


def _lint_reorder(
    op: ReorderOp, op_index: int, index: LintIndex
) -> tuple[EditOp | None, LintIssue | None, str]:
    """Lint a ``reorder`` op.

    Validates axis and target node existence.  The order list content is not
    validated against current widget/slot names (that's an apply concern).
    """
    target, issue = _resolve_node_target(
        index, op.target, op_index=op_index, op_kind="reorder",
    )
    if target is None:
        return None, issue, "rejected"

    # Validate axis (should always be valid since parse_edit_op enforces it)
    if op.axis not in ("widgets", "slots"):
        return None, _make_issue(
            "invalid_axis",
            f"Reorder axis must be 'widgets' or 'slots', got '{op.axis}'.",
            op_index=op_index,
            op_kind="reorder",
            scope_path=target.scope_path,
            uid=target.uid,
            detail={"axis": op.axis},
        ), "rejected"

    if target is op.target:
        return op, None, "passed"
    return ReorderOp(
        op="reorder", target=target, axis=op.axis, order=op.order,
    ), None, "passed"


def _lint_set_mode(
    op: SetModeOp, op_index: int, index: LintIndex
) -> tuple[EditOp | None, LintIssue | None, str]:
    """Lint a ``set_mode`` op.

    Validates target node and detects mode no-ops.
    """
    target, issue = _resolve_node_target(
        index, op.target, op_index=op_index, op_kind="set_mode",
    )
    if target is None:
        return None, issue, "rejected"

    # Check current mode
    node = index.node_by_uid(target.scope_path, target.uid)
    current_mode = node.get("mode") if node is not None else None

    if current_mode == op.mode:
        return None, _make_issue(
            "noop_mode",
            f"{_node_label(index, target.scope_path, target.uid)} is "
            f"already in mode {op.mode}.",
            severity="info",
            op_index=op_index,
            op_kind="set_mode",
            scope_path=target.scope_path,
            uid=target.uid,
            detail={"current_mode": current_mode, "requested_mode": op.mode},
        ), "dropped_noop"

    if target is op.target:
        return op, None, "passed"
    return SetModeOp(op="set_mode", target=target, mode=op.mode), None, "passed"


# ── main entry point ────────────────────────────────────────────────────────

def lint_delta(
    delta: Sequence[EditOp],
    index: LintIndex,
    schema_provider: Any = None,
) -> LintResult:
    """Lint a sequence of :class:`EditOp` objects against *index*.

    Parameters
    ----------
    delta:
        The ordered list of edit ops to lint (typically from a model response).
    index:
        A :class:`LintIndex` built from the *original_ui* that the delta
        targets.
    schema_provider:
        Optional schema provider for class-type and input-name validation
        on ``add_node`` ops.  When ``None`` (the default), schema checks
        are skipped.

    Returns
    -------
    LintResult:
        ``surviving`` is a tuple of ops that passed lint (possibly with
        LiteGraph ids rewritten to canonical uids).  ``issues`` collects
        every typed finding.  ``normalizations`` records the disposition of
        every original op.
    """
    surviving: list[EditOp] = []
    issues: list[LintIssue] = []
    normalizations: list[LintNormalization] = []

    _LINTERS: dict[str, Any] = {
        "set_node_field": _lint_set_node_field,
        "add_node": _lint_add_node,
        "remove_node": _lint_remove_node,
        "upsert_link": _lint_upsert_link,
        "remove_link": _lint_remove_link,
        "reorder": _lint_reorder,
        "set_mode": _lint_set_mode,
    }

    _SP_AWARE = frozenset({"add_node", "upsert_link", "remove_link"})

    for i, op in enumerate(delta):
        linter = _LINTERS.get(op.op)  # type: ignore[union-attr]
        if linter is None:
            issue = _make_issue(
                "unknown_op",
                f"Unknown edit operation '{op.op}'.",
                op_index=i,
                op_kind=getattr(op, "op", None),
            )
            issues.append(issue)
            normalizations.append(
                LintNormalization(op_index=i, op=op, disposition="rejected", issue=issue)
            )
            continue

        if op.op in _SP_AWARE:  # type: ignore[union-attr]
            normalized, issue, disposition = linter(op, i, index, schema_provider=schema_provider)
        else:
            normalized, issue, disposition = linter(op, i, index)
        if issue is not None:
            issues.append(issue)
        normalizations.append(
            LintNormalization(
                op_index=i,
                op=op,
                disposition=disposition,
                issue=issue,
            )
        )
        if disposition == "passed" and normalized is not None:
            surviving.append(normalized)

    return LintResult(
        surviving=tuple(surviving),
        issues=tuple(issues),
        normalizations=tuple(normalizations),
    )


__all__ = [
    "LintIndex",
    "LintIssue",
    "LintNormalization",
    "LintResult",
    "lint_delta",
]
