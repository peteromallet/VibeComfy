from __future__ import annotations

import re

from typing import TYPE_CHECKING, Any, Mapping

from vibecomfy.porting.edit._session_types import (
    InputSlotInfo,
    NodeDescriptor,
    OutputSlotInfo,
)
from vibecomfy.porting.edit._ir_utils import (
    _normalize_ir_type,
    _output_specs,
)
from vibecomfy.porting.edit._diff import _UNRESOLVED_OLD_VALUE
from vibecomfy.porting.edit.projection import HELPER_NODE_TYPES, MODE_LABELS
from vibecomfy.porting.edit.ops import LinkSourceRef
from vibecomfy.porting.edit.ledger import EditLedger
from vibecomfy.schema import schema_for

if TYPE_CHECKING:
    from vibecomfy.porting.emitter import NodeSignatureRow


class _DescribeMixin:
    """Describe and search: read-only introspection of the working graph."""

    # ------------------------------------------------------------------
    # Read-only queries (side-effect-free, never land ops)
    # ------------------------------------------------------------------

    def describe(self, name: str) -> NodeDescriptor:
        """Return a structured read-only description of the graph node named *name*.

        This method is side-effect-free: it does not mutate ``working_ui`` and
        does not record a landed operation.  It resolves *name* through the
        current ``uid_by_name`` / ``name_by_uid`` locks and the ledger.

        Returns a :class:`NodeDescriptor` with fields, inputs, outputs, socket
        types, mode, uid, placement, and virtual/helper status.
        """
        node_ref, issues = self._resolve_graph_name(name)
        if issues:
            raise LookupError(issues[0].message)
        assert node_ref is not None
        node = node_ref.node
        node_id = node.get("id")
        node_mode = node.get("mode", 0)
        mode_label = MODE_LABELS.get(node_mode, f"mode={node_mode}")
        class_type = node_ref.class_type
        is_helper = class_type in HELPER_NODE_TYPES

        # Virtual nodes are helpers that appear in the *original* ledger
        original_helper = False
        original_node = self.original_ledger.resolve_node(node_ref.scope_path, node_ref.uid)
        if original_node is not None:
            oc = str(original_node.get("type") or original_node.get("class_type") or "")
            original_helper = oc in HELPER_NODE_TYPES

        pos_raw = node.get("pos")
        pos: tuple[float, float] | None = None
        if isinstance(pos_raw, (list, tuple)) and len(pos_raw) == 2:
            try:
                pos = (float(pos_raw[0]), float(pos_raw[1]))
            except (TypeError, ValueError):
                pos = None

        size_raw = node.get("size")
        size: tuple[float, float] | None = None
        if isinstance(size_raw, (list, tuple)) and len(size_raw) == 2:
            try:
                size = (float(size_raw[0]), float(size_raw[1]))
            except (TypeError, ValueError):
                size = None

        title = node.get("title")
        if isinstance(title, str) and title:
            pass
        else:
            title = None

        widget_values_raw = node.get("widgets_values")
        if isinstance(widget_values_raw, list):
            widget_values = tuple(widget_values_raw)
        else:
            widget_values = ()

        # Build input slot info
        inputs_raw = node.get("inputs") or []
        fields: list[InputSlotInfo] = []
        schema = schema_for(self.schema_provider, class_type)
        schema_inputs = getattr(schema, "inputs", {}) or {}
        outgoing_links = self._outgoing_link_map(node_id)

        for idx, slot in enumerate(inputs_raw if isinstance(inputs_raw, list) else []):
            if not isinstance(slot, Mapping):
                continue
            slot_name = str(slot.get("name") or f"input_{idx}")
            slot_type = _normalize_ir_type(slot.get("type"))
            slot_link = slot.get("link")
            if isinstance(slot_link, (int, float)):
                slot_link = int(slot_link)
            else:
                slot_link = None
            # Determine widget_index: link to widget_values by position
            widget_idx = None
            if slot_name in schema_inputs:
                widget_idx = getattr(schema_inputs[slot_name], "widget", None)
                if widget_idx is not None:
                    try:
                        widget_idx = int(widget_idx)
                    except (TypeError, ValueError):
                        widget_idx = None
            fields.append(
                InputSlotInfo(
                    name=slot_name,
                    socket_type=slot_type,
                    link=slot_link,
                    is_virtual=slot.get("virtual", False) is True,
                    widget_index=widget_idx,
                )
            )

        # Build output slot info
        output_specs = _output_specs(node, self.schema_provider, class_type)
        outputs: list[OutputSlotInfo] = []
        for spec in output_specs:
            out_name = spec["name"]
            out_index = spec["index"]
            out_type = spec["type"]
            link_count = len(outgoing_links.get(out_index, []))
            outputs.append(
                OutputSlotInfo(
                    name=out_name,
                    slot_index=out_index,
                    socket_type=out_type,
                    link_count=link_count,
                )
            )

        return NodeDescriptor(
            name=node_ref.name,
            uid=node_ref.uid,
            scope_path=node_ref.scope_path,
            class_type=class_type,
            mode=node_mode,
            mode_label=mode_label,
            is_virtual=is_helper or original_helper,
            is_helper=is_helper,
            title=title,
            pos=pos,
            size=size,
            widget_values=widget_values,
            fields=tuple(fields),
            outputs=tuple(outputs),
        )

    def search(
        self,
        *,
        focus_types: list[str] | None = None,
        compatible_input_type: str | None = None,
        compatible_output_type: str | None = None,
        formatted: bool = False,
    ) -> list[NodeSignatureRow] | str:
        """Query available node signatures from the session's schema provider.

        This method is side-effect-free: it does not mutate ``working_ui`` and
        does not record a landed operation.

        Delegates to :func:`emit_available_node_signatures` with the
        session's ``schema_provider``.  When *formatted* is ``True``, returns a
        deterministic text catalog via :func:`format_signature_rows`.

        Parameters
        ----------
        focus_types:
            Optional list of class-type strings for per-node lookups.
            When ``None``, enumerates every known schema.
        compatible_input_type:
            Filter to rows that have at least one output compatible with this type.
        compatible_output_type:
            Filter to rows that have at least one input compatible with this type.
        formatted:
            When ``True``, return a formatted text string instead of a list of rows.
        """
        from vibecomfy.porting.emitter import emit_available_node_signatures, format_signature_rows as fmt_rows

        rows = emit_available_node_signatures(
            self.schema_provider,
            focus_types=focus_types,
            compatible_input_type=compatible_input_type,
            compatible_output_type=compatible_output_type,
        )
        if formatted:
            formatted_rows = fmt_rows(rows)
            if formatted_rows.strip() or not focus_types:
                return formatted_rows
            return self._format_empty_search_result(
                focus_types=focus_types,
                compatible_input_type=compatible_input_type,
                compatible_output_type=compatible_output_type,
            )
        return rows

    def _format_empty_search_result(
        self,
        *,
        focus_types: list[str],
        compatible_input_type: str | None = None,
        compatible_output_type: str | None = None,
    ) -> str:
        """Explain an exact schema lookup miss in agent-facing text."""
        from vibecomfy.schema import schemas_for

        requested = ", ".join(repr(item) for item in focus_types if isinstance(item, str))
        if not requested:
            requested = "<non-string focus type>"
        try:
            raw_schemas = schemas_for(self.schema_provider) or {}
        except Exception:
            raw_schemas = {}
        available = sorted(str(key) for key in raw_schemas if isinstance(key, str))
        requested_terms = [
            term.casefold()
            for item in focus_types
            if isinstance(item, str)
            for term in re.findall(r"[A-Za-z0-9]+", item)
            if len(term) >= 3
        ]
        close = [
            name
            for name in available
            if any(term in name.casefold() for term in requested_terms)
        ][:12]
        filter_bits: list[str] = []
        if compatible_input_type:
            filter_bits.append(f"compatible_input_type={compatible_input_type!r}")
        if compatible_output_type:
            filter_bits.append(f"compatible_output_type={compatible_output_type!r}")
        filter_note = f" with {' and '.join(filter_bits)}" if filter_bits else ""
        lines = [
            f"No node signature found for exact class type(s): {requested}{filter_note}.",
            "This search is a local ComfyUI schema lookup, not an internet or precedent search.",
        ]
        if close:
            lines.append("Available class names with similar terms: " + ", ".join(close) + ".")
        else:
            lines.append("No available local class names contain the requested terms.")
        lines.append(
            "Use one of the available node type names from the initial catalog, "
            "or stop with clarify(...) if the required custom node is absent."
        )
        return "\n".join(lines) + "\n"

    def python(self) -> str:
        """Return the current workflow as agent-edit Python.

        This query is side-effect-free with respect to graph edits: it does not
        record a landed operation or consume edit budget.
        """
        return self.render()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _outgoing_link_map(self, node_id: Any) -> dict[int, list[int]]:
        """Build a map from output slot index to list of link ids."""
        result: dict[int, list[int]] = {}
        if node_id is None:
            return result
        links = self.working_ui.get("links") or []
        if not isinstance(links, list):
            return result
        for link in links:
            if not isinstance(link, Mapping):
                continue
            origin_id = link.get("origin_id")
            origin_slot = link.get("origin_slot")
            link_id = link.get("id")
            if origin_id == node_id and isinstance(link_id, (int, float)):
                slot = 0
                if isinstance(origin_slot, (int, float)):
                    slot = int(origin_slot)
                result.setdefault(slot, []).append(int(link_id))
        return result

    # -- Gate C helpers --

    def _node_display_name(self, scope_path: str, uid: str) -> str:
        """Return the human-facing name for a node, preferring locked names."""
        return self.name_by_uid.get(uid, uid)

    def _node_class_type(self, scope_path: str, uid: str) -> str | None:
        """Look up the class_type of a node by uid from the working ledger."""
        node = self.ledger.resolve_node(scope_path or "", uid)
        if node is not None:
            return str(node.get("type") or node.get("class_type") or "")
        return None

    def _original_node_class_type(self, scope_path: str, uid: str) -> str | None:
        """Look up the class_type of a node from the original ledger."""
        node = self.original_ledger.resolve_node(scope_path or "", uid)
        if node is not None:
            return str(node.get("type") or node.get("class_type") or "")
        return None

    def _original_node_field_value(
        self, scope_path: str, uid: str, field: str
    ) -> Any:
        """Look up a widget value from the original ledger by field name."""
        node = self.original_ledger.resolve_node(scope_path or "", uid)
        if node is None:
            return _UNRESOLVED_OLD_VALUE
        return self._resolve_widget_value(node, field)

    def _node_field_value(
        self, scope_path: str, uid: str, field: str
    ) -> Any:
        """Look up a widget value by field name from the working ledger."""
        node = self.ledger.resolve_node(scope_path or "", uid)
        if node is None:
            return None
        return self._resolve_widget_value(node, field)

    def _resolve_widget_value(self, node: Mapping[str, Any], field: str) -> Any:
        """Resolve a widget value given a node dict and field name.

        Tries (a) node inputs slot ordering by name, (b) schema input ordering,
        since the schema may not carry ``widget`` metadata in test providers.
        """
        wv = node.get("widgets_values")
        if isinstance(wv, Mapping):
            return wv.get(field)
        if not isinstance(wv, list):
            return None
        # (a) Try inputs slot order first: find the slot named *field* and use its
        # positional index to index into widgets_values.
        inputs = node.get("inputs") or []
        if isinstance(inputs, list):
            for idx, slot in enumerate(inputs):
                if isinstance(slot, Mapping) and slot.get("name") == field:
                    if 0 <= idx < len(wv):
                        return wv[idx]
                    break
        # (b) Fall back to schema input ordering
        class_type = str(node.get("type") or node.get("class_type") or "")
        schema = schema_for(self.schema_provider, class_type)
        schema_inputs = getattr(schema, "inputs", {}) or {}
        if isinstance(schema_inputs, Mapping) and field in schema_inputs:
            # Get the positional index in the schema's input order
            ordered_names = list(schema_inputs.keys())
            try:
                idx = ordered_names.index(field)
                if 0 <= idx < len(wv):
                    return wv[idx]
            except ValueError:
                pass
        return None

    def _original_node_mode(self, scope_path: str, uid: str) -> Any:
        """Look up the original mode of a node from the original ledger."""
        node = self.original_ledger.resolve_node(scope_path or "", uid)
        if node is not None:
            return node.get("mode", 0)
        return _UNRESOLVED_OLD_VALUE

    def _original_link_value(self, scope_path: str, uid: str, input_field: str) -> Any:
        node = self.original_ledger.resolve_node(scope_path or "", uid)
        if node is None:
            return _UNRESOLVED_OLD_VALUE
        resolved = self._find_link_to_target_in_ledger(
            self.original_ledger, scope_path, uid, input_field
        )
        if resolved is None:
            return None
        src_uid, output_slot = resolved
        return {
            "scope_path": scope_path,
            "uid": src_uid,
            "output_slot": output_slot,
        }

    @staticmethod
    def _link_ref_value(source: LinkSourceRef) -> dict[str, Any]:
        return {
            "scope_path": source.scope_path,
            "uid": source.uid,
            "output_slot": source.output_slot,
        }

    def _node_mode(self, scope_path: str, uid: str) -> int:
        """Look up the current mode of a node from the working ledger."""
        node = self.ledger.resolve_node(scope_path or "", uid)
        if node is not None:
            return node.get("mode", 0)
        return 0

    def _output_socket_type(
        self, scope_path: str, uid: str, output_slot: str | int
    ) -> str | None:
        """Look up the socket type of an output slot."""
        node = self.ledger.resolve_node(scope_path or "", uid)
        if node is None:
            return None
        class_type = str(node.get("type") or node.get("class_type") or "")
        schema = schema_for(self.schema_provider, class_type)
        schema_outputs = getattr(schema, "outputs", []) or []
        if isinstance(slot_str := output_slot, int):
            if 0 <= slot_str < len(schema_outputs):
                return getattr(schema_outputs[slot_str], "type", None)
        else:
            for out in schema_outputs:
                if getattr(out, "name", None) == slot_str:
                    return getattr(out, "type", None)
        return None

    @staticmethod
    def _find_link_to_target_in_ledger(
        ledger: EditLedger, scope_path: str, uid: str, input_field: str
    ) -> tuple[str, str | int] | None:
        """Find the source (uid, output_slot) connected to a target input in a ledger.

        Returns None if no link exists.
        """
        node = ledger.resolve_node(scope_path or "", uid)
        if node is None:
            return None
        inputs = node.get("inputs") or []
        for slot in inputs:
            if not isinstance(slot, Mapping):
                continue
            if slot.get("name") == input_field:
                link = slot.get("link")
                if isinstance(link, (int, float)) and int(link) != 0:
                    link_id = int(link)
                    # Find the link in the graph
                    links = ledger.graph.get("links") or []
                    for l in links:
                        if not isinstance(l, list) or len(l) < 6:
                            continue
                        if l[0] == link_id:
                            src_uid = str(l[1])
                            src_slot = l[3]
                            return (src_uid, src_slot)
                break
        return None

    def _find_link_to_target(
        self, scope_path: str, uid: str, input_field: str
    ) -> tuple[str, str | int] | None:
        """Find the source (uid, output_slot) currently connected to a target input
        using the working ledger.

        Returns None if no link exists.
        """
        return self._find_link_to_target_in_ledger(
            self.ledger, scope_path, uid, input_field
        )

    def _adjacent_same_type_inputs(
        self, scope_path: str, exclude_field: str
    ) -> str | None:
        """If the working ledger has multiple inputs of the same type on any node,
        return a description of the adjacent same-type inputs for the given field.

        This is called during add-node summarization; it checks the target node
        being added to see if it has multiple inputs of the same type.
        """
        # This is harder to compute for add-node since the node isn't in the ledger yet.
        # We'll use the schema for the class_type of the node being constructed.
        return None
