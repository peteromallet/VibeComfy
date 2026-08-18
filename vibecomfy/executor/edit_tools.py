"""Typed edit tools for the one-step two-step execute loop (Hermes-style tool loop).

These replace the grammar-parse ``apply`` path.  Instead of the model emitting
a Python batch that a grammar must parse and guess at, the agent calls a small,
self-explanatory set of TYPED tools — ``edit_node`` / ``add_node`` /
``remove_node`` / ``upsert_link`` — and the host validates the arguments,
resolves the target by the NAME/UID the model saw in the render (names over
indices, philosophy #9), applies the edit copy-on-write to the retained
``VibeWorkflow`` IR, and returns a structured result (``ok``/``reason``/Δ id/
post-edit lens facts) that the next continuation sees in the session transcript.

Design discipline (philosophy #2, #5, #6, #9, #10):

* ONE authority — the retained IR (``EditSession.workflow``) is the only graph
  representation the tools read or mutate.  ``apply_edit_cow`` is copy-on-write
  (the pre-state IR is never mutated); the accepted Δ is re-emitted through the
  emit door and persisted onto the durable session transcript.
* Names over indices — ``target`` is a binding/uid from the render; positional
  ``widget_N`` references are rejected before dispatch.
* Boring over clever — the smallest tool set that covers the observed r3
  scenarios (set a named widget field, add + wire a node, remove a node,
  rewire an edge).  ``remove_link`` / ``set_node_mode`` are deliberately
  dropped: no observed scenario needs them, and the emit/verify gate already
  rejects orphaned wiring structurally.
* Deny-on-allowlist before dispatch, schema-validated args, structured
  ok/error results — the same discipline the research/advisory tools follow.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

# NOTE: the ``vibecomfy.porting.edit`` / ``vibecomfy.porting.render`` imports
# are LAZY (inside the builders/runtime) — importing them at module scope here
# re-enters ``porting.edit.ops`` during its own initialization (it imports
# ``comfy_nodes.agent.provider``), which breaks the ComfyUI route registration.

# The four typed edit tools.  ``remove_link`` / ``set_node_mode`` are NOT part
# of the set (see module docstring).
EDIT_TOOL_NAMES = frozenset({"edit_node", "add_node", "remove_node", "upsert_link"})

# Routes whose policy admits the Python edit capability (B02 ``allows_python_edits``).
EDIT_TOOL_ROUTES = frozenset({"revise", "adapt", "reorganise"})

# Positional widget references (``widget_2``, ``widget_12``) are never names.
_WIDGET_POSITIONAL_RE = re.compile(r"^widget_\d+$")


class EditToolError(ValueError):
    """A typed edit-tool rejection (argument/allowlist/target/CAS failure)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class EditToolOutcome:
    """The host's verdict for one typed edit-tool call.

    Mirrors the atomic-edit lifecycle: an accepted edit mints ONE Δ id and
    carries the post-edit emitted graph + lens facts; a rejection carries a
    stable ``reason`` and (once) a replacement permit.
    """

    ok: bool
    reason: str = ""
    delta_id: str | None = None
    op_dict: dict[str, Any] | None = None
    graph: Any = None
    lens_fact_ids: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()
    replacement_allowed: bool = False
    no_candidate: bool = False


# ── argument schemas (typed; validated before dispatch) ──────────────────────


_EDIT_TOOL_ARG_SCHEMAS: Mapping[str, tuple[frozenset[str], ...]] = {
    "edit_node": (frozenset({"target", "field", "value"}),),
    "add_node": (frozenset({"class_type", "name", "widget_values", "inputs"}),),
    "remove_node": (frozenset({"target"}),),
    "upsert_link": (frozenset({"source", "source_output", "target", "target_input"}),),
}

_EDIT_TOOL_REQUIRED: Mapping[str, frozenset[str]] = {
    "edit_node": frozenset({"target", "field"}),
    "add_node": frozenset({"class_type"}),
    "remove_node": frozenset({"target"}),
    "upsert_link": frozenset({"source", "target", "target_input"}),
}


def validate_edit_tool_args(tool: str, args: Any) -> dict[str, Any]:
    """Validate and normalize one edit-tool argument payload.

    A missing/blank required argument, an unknown keyword, or a non-mapping
    payload is a typed :class:`EditToolError` — never a handler KeyError and
    never a dispatch.
    """
    if tool not in EDIT_TOOL_NAMES:
        raise EditToolError("unknown_tool", f"unknown edit tool {tool!r}.")
    if not isinstance(args, Mapping):
        raise EditToolError("args_not_object", f"{tool} requires an args object.")
    normalized = dict(args)
    (allowed,) = _EDIT_TOOL_ARG_SCHEMAS[tool]
    unknown = sorted(set(normalized) - allowed)
    if unknown:
        raise EditToolError(
            "unknown_arg",
            f"{tool} does not accept argument(s): {', '.join(unknown)}.",
        )
    for name in sorted(_EDIT_TOOL_REQUIRED[tool]):
        value = normalized.get(name)
        if value is None or (isinstance(value, str) and not value.strip()):
            raise EditToolError(
                "arg_required",
                f"{tool} requires argument {name!r}.",
            )
    return normalized


def _reject_positional(value: str, *, path: str) -> None:
    if _WIDGET_POSITIONAL_RE.match(value):
        raise EditToolError(
            "positional_ref_rejected",
            f"{path} {value!r} is a positional widget ref — use the named "
            "field/binding shown in the render (names over indices).",
        )


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
        raise EditToolError("target_required", "target must be a non-empty name/uid.")
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
        "unknown_target",
        f"no node in the current render resolves to {target!r}.",
    )


# ── op builders ──────────────────────────────────────────────────────────────


def build_edit_op(edit_session: Any, tool: str, args: dict[str, Any]) -> Any:
    """Build one typed edit op from validated arguments (never applies it)."""
    from vibecomfy.porting.edit._ir_utils import _mint_ir_node_id, _mint_ir_uid  # noqa: PLC0415
    from vibecomfy.porting.edit.ops import (  # noqa: PLC0415
        AddNodeOp,
        LinkSourceRef,
        LinkTargetRef,
        NodeFieldTarget,
        NodeTarget,
        RemoveNodeOp,
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

    if tool == "upsert_link":
        source_uid = resolve_target(edit_session, args["source"])
        target_uid = resolve_target(edit_session, args["target"])
        source_output = args.get("source_output") or 0
        target_input = str(args["target_input"]).strip()
        _reject_positional(target_input, path="target_input")
        return UpsertLinkOp(
            op="upsert_link",
            source=LinkSourceRef(scope_path="", uid=source_uid, output_slot=source_output),
            target=LinkTargetRef(scope_path="", uid=target_uid, input_field=target_input),
        )

    if tool == "add_node":
        class_type = str(args["class_type"]).strip()
        workflow = getattr(edit_session, "workflow", None)
        uid = _mint_ir_uid(workflow) if workflow is not None else "n1"
        node_id = _mint_ir_node_id(workflow) if workflow is not None else "1"
        raw_widget_values = args.get("widget_values") or {}
        if not isinstance(raw_widget_values, Mapping):
            raise EditToolError(
                "bad_widget_values", "add_node widget_values must be an object."
            )
        fields = dict(raw_widget_values)
        inputs: dict[str, LinkSourceRef] = {}
        raw_inputs = args.get("inputs")
        if raw_inputs is not None:
            if not isinstance(raw_inputs, dict):
                raise EditToolError("bad_inputs", "add_node inputs must be an object.")
            for input_name, ref in raw_inputs.items():
                if isinstance(ref, (list, tuple)) and len(ref) >= 1:
                    source_name, output_slot = ref[0], (ref[1] if len(ref) > 1 else 0)
                else:
                    source_name, output_slot = ref, 0
                source_uid = resolve_target(edit_session, source_name)
                inputs[str(input_name)] = LinkSourceRef(
                    scope_path="", uid=source_uid, output_slot=output_slot
                )
        return AddNodeOp(
            op="add_node",
            scope_path="",
            class_type=class_type,
            fields=fields,
            inputs=inputs,
            uid=uid,
            node_id=node_id,
        )

    raise EditToolError("unknown_tool", f"unknown edit tool {tool!r}.")


# ── catalog docs (prompt CHANGE stage) ───────────────────────────────────────


def edit_tool_catalog_docs() -> str:
    """Prompt-doc bullet list for the typed edit tools (self-explanatory)."""
    return "\n".join(
        [
            "- `edit_node(target, field, value)` — set the named field on a node; "
            "``target`` is the name/uid from the render, ``field`` is a named "
            "widget/input key (never ``widget_N``).",
            "- `add_node(class_type, name?, widget_values?, inputs?)` — add a node; "
            "returns its binding. ``widget_values`` maps named widget/input keys to "
            "values; ``inputs`` maps an input name to a source binding (or "
            "``[binding, output]``).",
            "- `remove_node(target)` — remove the node named by ``target``.",
            "- `upsert_link(source, source_output, target, target_input)` — wire "
            "``source``'s output into ``target``'s named input (replaces any "
            "existing link into that input).",
        ]
    )


# ── the atomic edit runtime (one per message) ────────────────────────────────


class EditToolRuntime:
    """Per-message atomic edit authority over the retained IR.

    Holds the atomic lifecycle (one accepted edit, one replacement after a
    rejection) and applies validated typed ops copy-on-write onto the retained
    ``EditSession.workflow``.  Pure with respect to the session store: the
    caller persists the returned outcome (Δ id, ops, lens facts) onto the
    durable transcript.
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
        * a second rejection → ``second_rejection_no_candidate`` (no candidate);
        * one rejection permits exactly one replacement.
        """
        if self._accepted:
            return EditToolOutcome(ok=False, reason="edit_already_accepted")
        if self._rejections >= 2:
            return EditToolOutcome(
                ok=False,
                reason="second_rejection_no_candidate",
                no_candidate=True,
            )
        is_replacement = self._rejections == 1
        if is_replacement:
            self._replacement_used = True

        try:
            normalized = validate_edit_tool_args(tool, args)
            op = build_edit_op(self.edit_session, tool, normalized)
            from vibecomfy.porting.edit.ops import canonical_op_to_dict  # noqa: PLC0415

            op_dict = canonical_op_to_dict(op)
        except EditToolError as exc:
            return self._reject(exc.code, exc.message)
        except Exception as exc:  # noqa: BLE001 - typed rejection, never a raise
            return self._reject("invalid_edit", str(exc))

        if self.edit_session is None:
            return self._reject("no_edit_session", "this route has no retained IR to edit.")

        try:
            from vibecomfy.porting.edit._ir_utils import apply_edit_cow  # noqa: PLC0415
            from vibecomfy.porting.render import render_fact_pack  # noqa: PLC0415

            workflow = self.edit_session.workflow
            if workflow is None:
                return self._reject("no_edit_session", "this route has no retained IR to edit.")
            new_workflow = apply_edit_cow(
                workflow, op, schema_provider=getattr(self.edit_session, "schema_provider", None)
            )
            # Emit through the session's working-graph projector WITH the op so
            # pin_untouched_ui attributes the edited node (the old grammar path
            # did this via landed_ops); without attribution every node is pinned
            # to the ingest UI and the edit vanishes from the tool result.
            graph = self.edit_session._emit_working_snapshot(new_workflow, ops=(op,))
            fact_ids = tuple(
                str(ref.fact_id)
                for ref in render_fact_pack(new_workflow, lenses=("surface", "topology"))
            )
        except EditToolError:
            raise
        except Exception as exc:  # noqa: BLE001 - zero Δ: the edit is never partially applied
            return self._reject("apply_failed", str(exc))

        # Commit: the retained IR advances, one Δ is minted.
        self.edit_session.workflow = new_workflow
        self._accepted = True
        self._seq += 1
        delta_id = self._id_factory(self._seq)
        self._accepted_delta_ids = (delta_id,)
        self._last_graph = graph
        return EditToolOutcome(
            ok=True,
            reason="accepted",
            delta_id=delta_id,
            op_dict=op_dict,
            graph=graph,
            lens_fact_ids=fact_ids,
        )

    def _reject(self, reason: str, detail: str) -> EditToolOutcome:
        self._rejections += 1
        return EditToolOutcome(
            ok=False,
            reason=reason,
            diagnostics=(detail,),
            replacement_allowed=(self._rejections == 1),
            no_candidate=(self._rejections >= 2),
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
    "build_edit_op",
    "edit_tool_catalog_docs",
    "edit_tool_digest",
    "resolve_target",
    "validate_edit_tool_args",
]
