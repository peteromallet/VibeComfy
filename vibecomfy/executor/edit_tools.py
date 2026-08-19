"""Typed edit tools for the one-step two-step execute loop (Hermes-style tool loop).

These replace the grammar-parse ``apply`` path.  Instead of the model emitting
a Python batch that a grammar must parse and guess at, the agent calls a small,
self-explanatory set of TYPED tools — ``edit_node`` / ``add_node`` /
``remove_node`` / ``upsert_link`` / ``remove_link`` / ``set_node_mode`` /
``edit_batch`` — and the host validates the arguments against real per-tool
JSON Schemas, resolves the target by the NAME/UID the model saw in the render
(names over indices, philosophy #9), applies the edit through the shared
:meth:`EditSession.apply_ops` authority (schema/port check, no-op rejection,
structural checks, replay verification, emit/exit guard), and returns a stable
structured result (``ok``/``reason``/Δ id/bindings/lens facts/typed error) that
the next continuation sees in the session transcript.

Design discipline (philosophy #2, #5, #6, #9, #10):

* ONE authority — the retained IR (``EditSession.workflow``) is the only graph
  representation the tools read or mutate.  ``EditSession.apply_ops`` is
  copy-on-write (the pre-state IR is never mutated); the accepted Δ is
  re-emitted through the emit door and persisted onto the durable session
  transcript.
* Names over indices — ``target`` is a binding/uid from the render; positional
  ``widget_N`` references are rejected before dispatch.
* Deny-on-allowlist before dispatch, schema-validated args, structured
  ok/error results — the same discipline the research/advisory tools follow.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

# NOTE: the ``vibecomfy.porting.edit`` / ``vibecomfy.porting.render`` imports
# are LAZY (inside the builders/runtime) — importing them at module scope here
# re-enters ``porting.edit.ops`` during its own initialization (it imports
# ``comfy_nodes.agent.provider``), which breaks the ComfyUI route registration.

# The seven typed edit tools.
EDIT_TOOL_NAMES = frozenset(
    {"edit_node", "add_node", "remove_node", "upsert_link", "remove_link", "set_node_mode", "edit_batch"}
)

# Routes whose policy admits the Python edit capability (B02 ``allows_python_edits``).
EDIT_TOOL_ROUTES = frozenset({"revise", "adapt", "reorganise"})

# Positional widget references (``widget_2``, ``widget_12``) are never names.
_WIDGET_POSITIONAL_RE = re.compile(r"^widget_\d+$")

# Closed semantic mode enum for set_node_mode → LiteGraph mode integers.
_MODE_ENUM = frozenset({"enabled", "muted", "bypassed"})
_MODE_TO_LITEGRAPH = {"enabled": 0, "muted": 2, "bypassed": 4}

# Stable tool-loop error taxonomy (section 4).
_INVALID_ARGUMENTS = "invalid_arguments"
_UNKNOWN_TARGET = "unknown_target"
_UNKNOWN_FIELD = "unknown_field"
_UNKNOWN_PORT = "unknown_port"
_STALE_REVISION = "stale_revision"
_VERIFICATION_FAILED = "verification_failed"

_RETRYABLE_ERRORS = frozenset({_INVALID_ARGUMENTS, _UNKNOWN_TARGET, _UNKNOWN_FIELD, _UNKNOWN_PORT})

# Typed hydration failure: the render-visible {binding, uid, node_id} surface
# disagrees with the retained IR's resolver map.  Never consumes the model's
# replacement permit (the model was handed a broken vocabulary).
_HYDRATION_FAILURE = "hydration_failure"


class EditToolError(ValueError):
    """A typed edit-tool rejection (argument/allowlist/target/CAS failure)."""

    def __init__(self, code: str, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


@dataclass(frozen=True)
class EditToolOutcome:
    """The host's verdict for one typed edit-tool call.

    An accepted edit mints ONE Δ id and carries the post-edit emitted graph,
    lens facts, and any added-node bindings; a rejection carries a stable
    ``reason`` plus a structured ``error`` (code/message/retryable).
    """

    ok: bool
    reason: str = ""
    delta_id: str | None = None
    op_dicts: tuple[dict[str, Any], ...] = ()
    graph: Any = None
    lens_fact_ids: tuple[str, ...] = ()
    bindings: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()
    replacement_allowed: bool = False
    no_candidate: bool = False
    retryable: bool = False
    error: dict[str, Any] | None = None

    def structured_result(self, call_id: str, tool: str) -> dict[str, Any]:
        """The stable, durable structured result persisted to the transcript.

        ``{call_id, tool, ok, delta_id, bindings, lens_fact_ids, error}`` —
        never collapsed to a prose digest.
        """
        payload: dict[str, Any] = {
            "call_id": call_id,
            "tool": tool,
            "ok": self.ok,
            "delta_id": self.delta_id,
            "bindings": list(self.bindings),
            "lens_fact_ids": list(self.lens_fact_ids),
        }
        if self.ok:
            payload["error"] = None
        else:
            payload["error"] = self.error or {
                "code": self.reason or _VERIFICATION_FAILED,
                "message": (self.diagnostics[0] if self.diagnostics else self.reason or "rejected"),
                "retryable": self.retryable,
            }
        return payload


# ── per-tool JSON Schemas (discriminated union; validated before dispatch) ──

_STRING = {"type": "string"}
_OBJECT = {"type": "object"}

_EDIT_TOOL_ARG_SCHEMAS: Mapping[str, dict[str, Any]] = {
    "edit_node": {
        "type": "object",
        "required": ["target", "field", "value"],
        "properties": {"target": _STRING, "field": _STRING, "value": {}},
        "additionalProperties": False,
    },
    "add_node": {
        "type": "object",
        "required": ["class_type"],
        "properties": {
            "class_type": _STRING,
            "name": _STRING,
            "widget_values": _OBJECT,
            "inputs": _OBJECT,
        },
        "additionalProperties": False,
    },
    "remove_node": {
        "type": "object",
        "required": ["target"],
        "properties": {"target": _STRING},
        "additionalProperties": False,
    },
    "upsert_link": {
        "type": "object",
        "required": ["source", "target", "target_input"],
        "properties": {
            "source": _STRING,
            "source_output": {},
            "target": _STRING,
            "target_input": _STRING,
        },
        "additionalProperties": False,
    },
    "remove_link": {
        "type": "object",
        "required": ["target", "target_input"],
        "properties": {"target": _STRING, "target_input": _STRING},
        "additionalProperties": False,
    },
    "set_node_mode": {
        "type": "object",
        "required": ["target", "mode"],
        "properties": {"target": _STRING, "mode": {"type": "string", "enum": sorted(_MODE_ENUM)}},
        "additionalProperties": False,
    },
    "edit_batch": {
        "type": "object",
        "required": ["ops"],
        "properties": {"ops": {"type": "array"}},
        "additionalProperties": False,
    },
}


def _type_matches(spec: Mapping[str, Any] | None, value: Any) -> bool:
    if spec is None:
        return True
    spec_type = spec.get("type")
    if spec_type == "string":
        return isinstance(value, str)
    if spec_type == "object":
        return isinstance(value, Mapping)
    if spec_type == "array":
        return isinstance(value, (list, tuple))
    return True


def validate_edit_tool_args(tool: str, args: Any) -> dict[str, Any]:
    """Validate one edit-tool argument payload against its JSON Schema.

    A non-object payload, a missing required key, an unknown keyword, or a
    wrong-typed value is a typed :class:`EditToolError` (``invalid_arguments``)
    — never a handler KeyError and never a dispatch.  ``edit_node.value`` is
    REQUIRED (it may legitimately be ``0`` / ``False`` / ``\"\"``).
    """
    if tool not in EDIT_TOOL_NAMES:
        raise EditToolError("unknown_tool", f"unknown edit tool {tool!r}.", retryable=False)
    if not isinstance(args, Mapping):
        raise EditToolError(_INVALID_ARGUMENTS, f"{tool} requires an args object.")
    normalized = dict(args)
    schema = _EDIT_TOOL_ARG_SCHEMAS[tool]
    properties = schema.get("properties") or {}
    unknown = sorted(set(normalized) - set(properties))
    if unknown:
        raise EditToolError(
            _INVALID_ARGUMENTS,
            f"{tool} does not accept argument(s): {', '.join(unknown)}.",
        )
    for name in schema.get("required", ()):
        if name not in normalized:
            raise EditToolError(_INVALID_ARGUMENTS, f"{tool} requires argument {name!r}.")
    for name, spec in properties.items():
        if name not in normalized:
            continue
        if not _type_matches(spec, normalized[name]):
            raise EditToolError(
                _INVALID_ARGUMENTS,
                f"{tool} argument {name!r} must be a {spec.get('type')}.",
            )
        enum = spec.get("enum")
        if enum is not None and normalized[name] not in enum:
            raise EditToolError(
                _INVALID_ARGUMENTS,
                f"{tool} argument {name!r} must be one of: {', '.join(map(str, enum))}.",
            )
    if tool == "edit_batch":
        ops = normalized.get("ops")
        if not isinstance(ops, (list, tuple)) or not ops:
            raise EditToolError(_INVALID_ARGUMENTS, "edit_batch requires a non-empty `ops` list.")
        for index, op in enumerate(ops):
            if not isinstance(op, Mapping) or "op" not in op:
                raise EditToolError(
                    _INVALID_ARGUMENTS,
                    f"edit_batch.ops[{index}] must be an op object with an `op` key.",
                )
            sub_tool = str(op.get("op") or "")
            sub_args = {k: v for k, v in op.items() if k != "op"}
            validate_edit_tool_args(sub_tool, sub_args)
    return normalized


def _reject_positional(value: str, *, path: str) -> None:
    if _WIDGET_POSITIONAL_RE.match(value):
        raise EditToolError(
            _INVALID_ARGUMENTS,
            f"{path} {value!r} is a positional widget ref — use the named "
            "field/binding shown in the render (names over indices).",
        )


def render_resolver_parity_issues(edit_session: Any) -> tuple[str, ...]:
    """Render-visible {binding, uid, node_id} vs the retained-IR resolver map.

    The render (``surface``/``topology`` lenses) is the ONLY vocabulary the
    model sees; the resolver map (``uid_by_name`` + IR nodes) is the ONLY
    vocabulary the edit tools accept.  When the two disagree the session is
    mis-hydrated: every render-visible ref would be rejected and the model's
    single replacement permit would be burned for no reason.  Both sides are
    derived through the SAME named ingest door (``_named_import``) — the
    render side exactly as the message render does (``use_comfy_converter=False``,
    no schema provider), the resolver side from the retained IR — so a
    non-empty return is a typed hydration failure, never a vocabulary guess.
    """
    if edit_session is None:
        return ()
    workflow = getattr(edit_session, "workflow", None)
    if workflow is None or not getattr(workflow, "nodes", None):
        return ()
    raw_ui = getattr(edit_session, "original_ui", None)
    if not isinstance(raw_ui, Mapping) or not raw_ui:
        return ()
    from vibecomfy.ingest.normalize import (  # noqa: PLC0415
        _assert_nonempty_ingest_preserved,
        _named_import,
    )
    from vibecomfy.porting.emit.emit_kwargs import _compute_variable_names  # noqa: PLC0415

    try:
        rendered = _named_import(dict(raw_ui), use_comfy_converter=False)
        _assert_nonempty_ingest_preserved(raw_ui, rendered)
    except Exception:  # noqa: BLE001 - cannot prove a mismatch; render is best-effort
        return ()

    uid_by_name = getattr(edit_session, "uid_by_name", None) or {}
    ir_nodes = getattr(workflow, "nodes", None) or {}
    uid_to_node_id: dict[str, str] = {}
    for nid, node in ir_nodes.items():
        uid = str(getattr(node, "uid", "") or "")
        if uid:
            uid_to_node_id.setdefault(uid, str(nid))
    try:
        render_bindings = _compute_variable_names(rendered.nodes, list(rendered.edges))
    except Exception:  # noqa: BLE001 - binding derivation is best-effort
        render_bindings = {}

    issues: list[str] = []
    for nid, node in (rendered.nodes or {}).items():
        uid = str(getattr(node, "uid", "") or "")
        binding = render_bindings.get(str(nid), "")
        if uid:
            resolved_uid = uid_by_name.get(binding)
            if resolved_uid != uid:
                issues.append(
                    f"render shows binding {binding!r} for uid {uid!r} but the "
                    f"retained IR's resolver map binds it to {resolved_uid!r}"
                )
            if uid not in uid_to_node_id:
                issues.append(
                    f"render shows uid {uid!r} which the retained IR does not contain"
                )
            elif uid_to_node_id[uid] != str(nid):
                issues.append(
                    f"render shows node_id {nid!r} for uid {uid!r} but the retained "
                    f"IR maps that uid to node_id {uid_to_node_id[uid]!r}"
                )
        elif str(nid) not in ir_nodes:
            issues.append(
                f"render shows node_id {nid!r} which the retained IR does not contain"
            )
    return tuple(issues)


# ── name/uid resolution (names over indices) ─────────────────────────────────


def resolve_target(edit_session: Any, target: Any) -> str:
    """Resolve a render-visible node reference to a retained-IR uid.

    * a binding name (``cliptextencode``) → ``uid_by_name``;
    * a uid shown in the render (``n1``) → itself, when present in the IR;
    * a numeric node id → that node's uid.

    ``widget_N`` positional refs are rejected before any lookup (philosophy #9).
    """
    target = str(target or "").strip()
    if not target:
        raise EditToolError(_INVALID_ARGUMENTS, "target must be a non-empty name/uid.")
    _reject_positional(target, path="target")

    workflow = getattr(edit_session, "workflow", None)
    uid_by_name = getattr(edit_session, "uid_by_name", None) or {}
    if target in uid_by_name:
        return str(uid_by_name[target])
    if workflow is not None:
        for node_id, node in (workflow.nodes or {}).items():
            uid = str(getattr(node, "uid", "") or "")
            if uid == target:
                return uid
            if str(node_id) == target:
                return uid or str(node_id)
    raise EditToolError(
        _UNKNOWN_TARGET,
        f"no node in the current render resolves to {target!r}.",
    )


# ── op builders ──────────────────────────────────────────────────────────────


def build_single_op(edit_session: Any, tool: str, args: dict[str, Any]) -> Any:
    """Build one typed edit op from validated arguments (never applies it)."""
    from vibecomfy.porting.edit._ir_utils import _mint_ir_node_id, _mint_ir_uid  # noqa: PLC0415
    from vibecomfy.porting.edit.ops import (  # noqa: PLC0415
        AddNodeOp,
        LinkSourceRef,
        LinkTargetRef,
        NodeFieldTarget,
        NodeTarget,
        RemoveLinkOp,
        RemoveNodeOp,
        SetModeOp,
        SetNodeFieldOp,
        UpsertLinkOp,
    )

    if tool == "edit_node":
        field = str(args["field"]).strip()
        _reject_positional(field, path="field")
        uid = resolve_target(edit_session, args["target"])
        return SetNodeFieldOp(
            op="set_node_field",
            target=NodeFieldTarget(scope_path="", uid=uid, field_path=field),
            value=args["value"],
        )

    if tool == "remove_node":
        uid = resolve_target(edit_session, args["target"])
        return RemoveNodeOp(op="remove_node", target=NodeTarget(scope_path="", uid=uid))

    if tool == "set_node_mode":
        uid = resolve_target(edit_session, args["target"])
        mode = _MODE_TO_LITEGRAPH[str(args["mode"]).strip()]
        return SetModeOp(op="set_mode", target=NodeTarget(scope_path="", uid=uid), mode=mode)

    if tool == "upsert_link":
        source_uid = resolve_target(edit_session, args["source"])
        target_uid = resolve_target(edit_session, args["target"])
        source_output = args.get("source_output")
        if source_output is None or source_output == "":
            source_output = 0
        target_input = str(args["target_input"]).strip()
        _reject_positional(target_input, path="target_input")
        return UpsertLinkOp(
            op="upsert_link",
            source=LinkSourceRef(scope_path="", uid=source_uid, output_slot=source_output),
            target=LinkTargetRef(scope_path="", uid=target_uid, input_field=target_input),
        )

    if tool == "remove_link":
        target_uid = resolve_target(edit_session, args["target"])
        target_input = str(args["target_input"]).strip()
        _reject_positional(target_input, path="target_input")
        return RemoveLinkOp(
            op="remove_link",
            target=LinkTargetRef(scope_path="", uid=target_uid, input_field=target_input),
        )

    if tool == "add_node":
        class_type = str(args["class_type"]).strip()
        workflow = getattr(edit_session, "workflow", None)
        uid = _mint_ir_uid(workflow) if workflow is not None else "n1"
        node_id = _mint_ir_node_id(workflow) if workflow is not None else "1"
        raw_widget_values = args.get("widget_values") or {}
        if not isinstance(raw_widget_values, Mapping):
            raise EditToolError(_INVALID_ARGUMENTS, "add_node widget_values must be an object.")
        fields = dict(raw_widget_values)
        inputs: dict[str, LinkSourceRef] = {}
        raw_inputs = args.get("inputs")
        if raw_inputs is not None:
            if not isinstance(raw_inputs, dict):
                raise EditToolError(_INVALID_ARGUMENTS, "add_node inputs must be an object.")
            for input_name, ref in raw_inputs.items():
                if isinstance(ref, (list, tuple)) and len(ref) >= 1:
                    source_name, output_slot = ref[0], (ref[1] if len(ref) > 1 else 0)
                else:
                    source_name, output_slot = ref, 0
                source_uid = resolve_target(edit_session, source_name)
                inputs[str(input_name)] = LinkSourceRef(
                    scope_path="", uid=source_uid, output_slot=output_slot
                )
        name = args.get("name")
        return AddNodeOp(
            op="add_node",
            scope_path="",
            class_type=class_type,
            fields=fields,
            inputs=inputs,
            uid=uid,
            node_id=node_id,
            title=str(name).strip() if name else None,
            # Record the field ORDER as the canonical widget order so a
            # schema-less replay maps named fields positionally to
            # ``widgets_values`` (Codex generalization fix).
            widget_field_names=tuple(fields.keys()),
        )

    raise EditToolError("unknown_tool", f"unknown edit tool {tool!r}.", retryable=False)


def build_edit_ops(edit_session: Any, tool: str, args: dict[str, Any]) -> tuple[Any, ...]:
    """Build the typed op(s) for one validated tool call.

    ``edit_batch`` lowers to a tuple of ops (one durable Δ); every other tool
    lowers to a single-op tuple.  Batch sub-ops are built against the
    SEQUENTIAL IR state — each sub-op sees the previous sub-op's effect for
    uid minting and target resolution (two ``add_node`` entries mint distinct
    uids; add-then-link resolves the new node) — while the batch is still
    validated and applied atomically by :meth:`EditSession.apply_ops`.
    """
    if tool != "edit_batch":
        return (build_single_op(edit_session, tool, args),)

    running = _SequentialBuildSession(edit_session)
    ops: list[Any] = []
    for entry in args["ops"]:
        sub_tool = str(entry.get("op") or "")
        sub_args = {k: v for k, v in entry.items() if k != "op"}
        op = build_single_op(running, sub_tool, sub_args)
        ops.append(op)
        running.apply(op)
    return tuple(ops)


class _SequentialBuildSession:
    """A read-mostly EditSession facade exposing a running IR for batch builds.

    ``build_single_op`` reads ``edit_session.workflow`` (uid/node-id minting)
    and ``edit_session.uid_by_name`` (target resolution).  This facade advances
    a COW copy of the retained IR after each built op so later sub-ops see the
    prior sub-op's node(s)/bindings, without mutating the real session (the
    real IR advances only when ``apply_ops`` accepts the whole batch).
    """

    def __init__(self, edit_session: Any) -> None:
        self._base = edit_session
        self.schema_provider = getattr(edit_session, "schema_provider", None)
        base_workflow = getattr(edit_session, "workflow", None)
        if base_workflow is None:
            self.workflow = None
        else:
            from vibecomfy.porting.edit._ir_utils import (  # noqa: PLC0415
                _cow_workflow_copy,
            )

            self.workflow = _cow_workflow_copy(base_workflow)
        # Transient local-alias index (P2): an ``add_node``'s ``name`` arg is
        # the model's LOCAL alias for the minted uid.  It is registered ONLY
        # here — never persisted into the retained IR, the emit snapshot, or
        # the resolver map of any later message — so later sub-ops in the SAME
        # batch can resolve the new node by the alias they just chose.  This is
        # not a second authority: it never overrides a class-derived binding.
        self._local_aliases: dict[str, str] = {}

    @property
    def uid_by_name(self) -> dict[str, str]:
        from vibecomfy.porting.emit.emit_kwargs import (  # noqa: PLC0415
            _compute_variable_names,
        )

        if self.workflow is None:
            return {}
        try:
            names = _compute_variable_names(self.workflow.nodes, list(self.workflow.edges))
        except Exception:  # noqa: BLE001 - binding derivation is best-effort
            names = {}
        name_to_uid: dict[str, str] = {}
        for node_id, name in names.items():
            node = self.workflow.nodes.get(node_id)
            uid = str(getattr(node, "uid", "") or "")
            if uid:
                name_to_uid.setdefault(name, uid)
        # Class-derived bindings win; local aliases only fill gaps (so an alias
        # can never hijack another node's render-visible name).
        for alias, uid in self._local_aliases.items():
            name_to_uid.setdefault(alias, uid)
        return name_to_uid

    def apply(self, op: Any) -> None:
        """Advance the running IR past *op* (best-effort; never fatal)."""
        if self.workflow is None:
            return
        from vibecomfy.porting.edit._ir_utils import apply_edit_cow  # noqa: PLC0415

        try:
            self.workflow = apply_edit_cow(
                self.workflow, op, schema_provider=self.schema_provider
            )
        except Exception:  # noqa: BLE001 - an invalid sub-op is rejected atomically later
            return
        # P2: register the add_node's local alias → the uid THIS batch minted.
        # The alias never leaves this facade (see ``uid_by_name``).
        if getattr(op, "op", "") == "add_node" and getattr(op, "uid", ""):
            title = str(getattr(op, "title", "") or "").strip()
            if title:
                self._local_aliases.setdefault(title, str(op.uid))


# ── catalog docs (prompt CHANGE stage) ───────────────────────────────────────


def edit_tool_catalog_docs() -> str:
    """Prompt-doc bullet list for the typed edit tools (self-explanatory)."""
    return "\n".join(
        [
            "- `edit_node(target, field, value)` — set the named field on a node; "
            "``target`` is the name/uid from the render, ``field`` is a named "
            "widget/input key (never ``widget_N``).",
            "- `add_node(class_type, name?, widget_values?, inputs?)` — add a node; "
            "returns its uid binding. ``widget_values`` maps named widget/input keys to "
            "values; ``inputs`` maps an input name to a source binding (or "
            "``[binding, output]``).",
            "- `remove_node(target)` — remove the node named by ``target``.",
            "- `upsert_link(source, source_output, target, target_input)` — wire "
            "``source``'s output into ``target``'s named input (replaces any "
            "existing link into that input).",
            "- `remove_link(target, target_input)` — disconnect the named input "
            "of ``target`` (intentional absence).",
            "- `set_node_mode(target, mode)` — set the node mode to "
            "``enabled`` | ``muted`` | ``bypassed``.",
            "- `edit_batch(ops=[...])` — apply several typed edits atomically as "
            "ONE accepted Δ; each ``ops`` entry is an op object like "
            "``{\"op\": \"edit_node\", \"target\": ..., \"field\": ..., \"value\": ...}``.",
        ]
    )


# ── the atomic edit runtime (one per message) ────────────────────────────────


class EditToolRuntime:
    """Per-message atomic edit authority over the retained IR.

    Holds the atomic lifecycle (one accepted edit, one replacement after a
    semantic rejection) and applies validated typed ops through the shared
    :meth:`EditSession.apply_ops` authority.  Malformed arguments are
    corrected WITHOUT consuming the replacement (they never reach ``apply_ops``);
    a semantic rejection (schema/port/no-op/structural/replay/exit-guard) does
    consume it.  Pure with respect to the session store: the caller persists
    the returned outcome (Δ id, ops, lens facts) onto the durable transcript.
    """

    def __init__(self, *, edit_session: Any, id_factory: Any | None = None) -> None:
        self.edit_session = edit_session
        self._id_factory = id_factory or (lambda seq: f"d{seq}")
        self._accepted = False
        self._rejections = 0
        self._replacement_used = False
        self._seq = 0
        self._accepted_delta_ids: tuple[str, ...] = ()
        self._last_graph: Any = None
        self._last_bindings: tuple[str, ...] = ()
        # P2: at MESSAGE START assert parity between the render-visible
        # {binding, uid, node_id} surface and the retained IR's resolver map.
        # A mismatch is a typed hydration failure: every dispatch returns
        # ``hydration_failure`` WITHOUT consuming the replacement permit.
        self._hydration_issues = render_resolver_parity_issues(edit_session)

    # -- queries -------------------------------------------------------------

    @property
    def accepted(self) -> bool:
        return self._accepted

    @property
    def accepted_delta_ids(self) -> tuple[str, ...]:
        return self._accepted_delta_ids

    @property
    def replacement_used(self) -> bool:
        return self._replacement_used

    @property
    def graph(self) -> Any:
        return self._last_graph

    @property
    def bindings(self) -> tuple[str, ...]:
        return self._last_bindings

    @property
    def hydration_failed(self) -> bool:
        """True when the message-start render/resolver parity assertion failed."""
        return bool(self._hydration_issues)

    def workflow(self) -> Any:
        return getattr(self.edit_session, "workflow", None) if self.edit_session else None

    def render_text(self) -> str | None:
        workflow = self.workflow()
        if workflow is None:
            return None
        try:
            from vibecomfy.porting.render import render_text  # noqa: PLC0415

            return render_text(workflow, lenses=("surface", "topology"))
        except Exception:  # noqa: BLE001 - render is best-effort prompt context
            return None

    # -- mutation ------------------------------------------------------------

    def dispatch(self, tool: str, args: Mapping[str, Any]) -> EditToolOutcome:
        """Gate, validate, and apply one edit-tool call (atomic lifecycle).

        * a second edit after acceptance → ``edit_already_accepted``;
        * a second semantic rejection → ``second_rejection_no_candidate``;
        * malformed arguments → ``invalid_arguments`` (retryable; the single
          replacement permit is NOT consumed);
        * one semantic rejection permits exactly one replacement.
        """
        if self._hydration_issues:
            # Typed hydration failure (P2): the render-visible vocabulary the
            # model was handed does not match the retained IR's resolver map.
            # This is a HOST defect, not an edit attempt: it never consumes
            # the replacement permit and never advances the rejection counter.
            detail = (
                "render/resolver parity mismatch (typed hydration failure): "
                + "; ".join(self._hydration_issues[:3])
            )
            return EditToolOutcome(
                ok=False,
                reason=_HYDRATION_FAILURE,
                diagnostics=(detail,),
                retryable=True,
                error={"code": _HYDRATION_FAILURE, "message": detail, "retryable": True},
            )
        if self._accepted:
            return EditToolOutcome(ok=False, reason="edit_already_accepted", retryable=False)
        if self._rejections >= 2:
            return EditToolOutcome(
                ok=False,
                reason="second_rejection_no_candidate",
                no_candidate=True,
                retryable=False,
            )

        try:
            normalized = validate_edit_tool_args(tool, args)
        except EditToolError as exc:
            return self._reject_args(exc.code, exc.message, exc.retryable)
        except Exception as exc:  # noqa: BLE001 - typed rejection, never a raise
            return self._reject_args(_INVALID_ARGUMENTS, str(exc), True)

        try:
            ops = build_edit_ops(self.edit_session, tool, normalized)
            from vibecomfy.porting.edit.ops import canonical_op_to_dict  # noqa: PLC0415

            op_dicts = tuple(canonical_op_to_dict(op) for op in ops)
        except EditToolError as exc:
            # Argument-shape errors (positional ``widget_N`` refs, blank refs)
            # are malformed input, not an edit attempt: they never consume the
            # one replacement window.  Only genuine resolution failures
            # (unknown_target / unknown_field / unknown_port) are semantic.
            if exc.code == _INVALID_ARGUMENTS:
                return self._reject_args(exc.code, exc.message, exc.retryable)
            # Semantic resolution failure (unknown target/field/port): this IS
            # an edit attempt — it consumes the one replacement window.
            return self._reject(exc.code, exc.message, retryable=exc.retryable)
        except Exception as exc:  # noqa: BLE001 - typed rejection, never a raise
            return self._reject(_INVALID_ARGUMENTS, str(exc), retryable=True)

        if self.edit_session is None:
            return self._reject("no_edit_session", "this route has no retained IR to edit.")

        # This is a real semantic attempt: if we are inside the one-replacement
        # window, it now counts as the replacement.
        is_replacement = self._rejections == 1
        if is_replacement:
            self._replacement_used = True

        try:
            result = self.edit_session.apply_ops(ops)
        except Exception as exc:  # noqa: BLE001 - infra failure, retryable
            return self._reject("apply_failed", str(exc), retryable=True)

        if not result.ok:
            diagnostics = tuple(str(d.message) if hasattr(d, "message") else str(d) for d in result.diagnostics)
            return self._reject(result.reason, " | ".join(diagnostics) or result.reason, retryable=result.retryable)

        # Commit: the retained IR advances, one Δ is minted.
        self._accepted = True
        self._seq += 1
        delta_id = self._id_factory(self._seq)
        self._accepted_delta_ids = (delta_id,)
        self._last_graph = result.graph
        fact_ids: tuple[str, ...] = ()
        try:
            from vibecomfy.porting.render import render_fact_pack  # noqa: PLC0415

            fact_ids = tuple(
                str(ref.fact_id)
                for ref in render_fact_pack(result.workflow, lenses=("surface", "topology"))
            )
        except Exception:  # noqa: BLE001 - fact pack is best-effort context
            fact_ids = ()
        bindings = tuple(
            str(getattr(op, "uid", "") or "")
            for op in ops
            if getattr(op, "uid", "") and getattr(op, "op", "") == "add_node"
        )
        self._last_bindings = bindings
        return EditToolOutcome(
            ok=True,
            reason="accepted",
            delta_id=delta_id,
            op_dicts=op_dicts,
            graph=result.graph,
            lens_fact_ids=fact_ids,
            bindings=bindings,
        )

    def _reject(self, reason: str, detail: str, *, retryable: bool = False) -> EditToolOutcome:
        self._rejections += 1
        return EditToolOutcome(
            ok=False,
            reason=reason,
            diagnostics=(detail,),
            replacement_allowed=(self._rejections == 1),
            no_candidate=(self._rejections >= 2),
            retryable=retryable,
            error={"code": reason, "message": detail, "retryable": retryable},
        )

    def _reject_args(self, reason: str, detail: str, retryable: bool) -> EditToolOutcome:
        """Malformed-arguments rejection: never consumes the replacement."""
        return EditToolOutcome(
            ok=False,
            reason=reason,
            diagnostics=(detail,),
            replacement_allowed=(self._rejections < 2),
            no_candidate=(self._rejections >= 2),
            retryable=retryable,
            error={"code": reason, "message": detail, "retryable": retryable},
        )


def edit_tool_digest(tool: str, args: Mapping[str, Any], outcome: EditToolOutcome) -> str:
    """Compact transcript digest for one edit-tool result (never raw bodies)."""
    summary = ", ".join(f"{k}={v!r}" for k, v in sorted(args.items()))
    if outcome.ok:
        return f"{tool}({summary}) — ok: Δ={outcome.delta_id}"
    suffix = ""
    if outcome.replacement_allowed:
        suffix = " (one replacement allowed)"
    if outcome.no_candidate:
        suffix = " (no candidate — do not submit another edit)"
    return f"{tool}({summary}) — rejected: {outcome.reason}{suffix}"


__all__ = [
    "EDIT_TOOL_NAMES",
    "EDIT_TOOL_ROUTES",
    "EditToolError",
    "EditToolOutcome",
    "EditToolRuntime",
    "build_edit_ops",
    "build_single_op",
    "edit_tool_catalog_docs",
    "edit_tool_digest",
    "resolve_target",
    "validate_edit_tool_args",
]
