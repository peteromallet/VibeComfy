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
from vibecomfy.porting.widgets.compact_resolver import (
    missing_widget_value_sentinel,
    widget_value_for_field,
)
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

        This method is side-effect-free: it does not mutate the retained IR
        (or the emit-side JSON snapshot) and does not record a landed
        operation.  It resolves *name* through the deterministic
        ``(class_type, uid-order)`` bindings on the retained IR and reads
        fields from :class:`~vibecomfy.porting.edit.editable_surface.EditableSurface`.

        Returns a :class:`NodeDescriptor` with fields, inputs, outputs, socket
        types, mode, uid, placement, and virtual/helper status.
        """
        from vibecomfy.porting.edit.editable_surface import editable_surface_for
        from vibecomfy.workflow import mode_to_litegraph

        node_ref, issues = self._resolve_graph_name(name)
        if issues:
            raise LookupError(issues[0].message)
        assert node_ref is not None
        ir_node = self._ir_node_by_uid(node_ref.uid)
        if ir_node is None:
            raise LookupError(f"Graph name {name!r} has no retained-IR node.")
        class_type = str(getattr(ir_node, "class_type", "") or node_ref.class_type)
        is_helper = class_type in HELPER_NODE_TYPES
        original_helper = False
        original_node = self.original_ledger.resolve_node(node_ref.scope_path, node_ref.uid)
        if original_node is not None:
            oc = str(original_node.get("type") or original_node.get("class_type") or "")
            original_helper = oc in HELPER_NODE_TYPES

        node_mode = mode_to_litegraph(getattr(ir_node, "mode", 0))
        mode_label = MODE_LABELS.get(node_mode, f"mode={node_mode}")
        pos = self._pair_float(getattr(ir_node, "pos", None))
        size = self._pair_float(getattr(ir_node, "size", None))
        title = self._ir_node_title(ir_node)
        widget_values = self._ir_widget_values(ir_node)
        workflow = getattr(self, "workflow", None)
        surface = editable_surface_for(
            ir_node,
            schema_provider=self.schema_provider,
            edges=getattr(workflow, "edges", None),
        )
        incoming = self._ir_incoming_link_ids(ir_node)
        fields: list[InputSlotInfo] = []
        for slot in surface.inputs:
            fields.append(
                InputSlotInfo(
                    name=slot.name,
                    socket_type=slot.socket_type,
                    link=incoming.get(slot.name),
                    is_virtual=False,
                )
            )
        outgoing = self._ir_outgoing_by_port(ir_node)
        outputs: list[OutputSlotInfo] = []
        for index, port in enumerate(surface.outputs):
            outputs.append(
                OutputSlotInfo(
                    name=port.name,
                    slot_index=index,
                    socket_type=port.socket_type,
                    link_count=len(outgoing.get(port.name, ())),
                )
            )
        if not outputs:
            output_specs = _output_specs(
                self._ir_node_as_mapping(ir_node),
                self.schema_provider,
                class_type,
            )
            for spec in output_specs:
                outputs.append(
                    OutputSlotInfo(
                        name=spec["name"],
                        slot_index=spec["index"],
                        socket_type=spec["type"],
                        link_count=len(outgoing.get(spec["name"], ())),
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
        in_graph_nodes: Any = None,
    ) -> list[NodeSignatureRow] | str:
        """Query available node signatures from the session's schema provider.

        This method is side-effect-free: it does not mutate the retained IR
        and does not record a landed operation.

        Delegates to :func:`emit_available_node_signatures` with the
        session's ``schema_provider``.  When *formatted* is ``True``, returns a
        deterministic text catalog via :func:`format_signature_rows`.

        When *in_graph_nodes* is omitted, the retained IR is used.  Literal
        fields that no in-graph node of a class can resolve are dropped from
        that class's row so the catalog does not advertise schema-drifted
        fields as writable.  Socket inputs are never dropped.

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
        from vibecomfy.porting.authoring_names import constructor_aliases_for_schema_provider
        from vibecomfy.porting.emitter import (
            emit_available_node_signatures,
            filter_signature_rows_to_in_graph_nodes,
            format_signature_rows as fmt_rows,
        )

        rows = emit_available_node_signatures(
            self.schema_provider,
            focus_types=focus_types,
            compatible_input_type=compatible_input_type,
            compatible_output_type=compatible_output_type,
        )
        if in_graph_nodes is None:
            workflow = getattr(self, "workflow", None)
            if workflow is not None and getattr(workflow, "nodes", None):
                in_graph_nodes = workflow
        if in_graph_nodes is not None:
            rows = filter_signature_rows_to_in_graph_nodes(rows, in_graph_nodes)
        if formatted:
            formatted_rows = fmt_rows(
                rows,
                class_type_aliases=constructor_aliases_for_schema_provider(self.schema_provider),
            )
            if not focus_types and (compatible_input_type or compatible_output_type) and rows:
                index = self._format_compatibility_search_index(
                    rows,
                    compatible_input_type=compatible_input_type,
                    compatible_output_type=compatible_output_type,
                )
                formatted_rows = f"{index}\n\n{formatted_rows}" if formatted_rows.strip() else index
            if formatted_rows.strip():
                if focus_types:
                    found = {row.class_type for row in rows}
                    missing = [
                        class_type
                        for class_type in focus_types
                        if isinstance(class_type, str) and class_type not in found
                    ]
                    related = self._format_focus_type_related_hints(
                        focus_types=focus_types,
                        rows=rows,
                    )
                    if related:
                        formatted_rows = (
                            formatted_rows.rstrip()
                            + "\n\n"
                            + related.rstrip()
                            + "\n"
                        )
                    if missing:
                        formatted_rows = (
                            formatted_rows.rstrip()
                            + "\n\n"
                            + self._format_empty_search_result(
                                focus_types=missing,
                                compatible_input_type=compatible_input_type,
                                compatible_output_type=compatible_output_type,
                            ).rstrip()
                            + "\n"
                        )
                return formatted_rows
            if not focus_types:
                return formatted_rows
            return self._format_empty_search_result(
                focus_types=focus_types,
                compatible_input_type=compatible_input_type,
                compatible_output_type=compatible_output_type,
            )
        return rows

    def _format_compatibility_search_index(
        self,
        rows: list[NodeSignatureRow],
        *,
        compatible_input_type: str | None = None,
        compatible_output_type: str | None = None,
    ) -> str:
        names = sorted(
            {
                row.class_type
                for row in rows or []
                if isinstance(getattr(row, "class_type", None), str)
                and row.class_type
            }
        )
        filter_bits: list[str] = []
        if compatible_input_type:
            filter_bits.append(f"outputs compatible with {compatible_input_type!r}")
        if compatible_output_type:
            filter_bits.append(f"inputs compatible with {compatible_output_type!r}")
        filter_label = " and ".join(filter_bits) if filter_bits else "matching compatibility filter"
        lines = [f"Matching local class types ({len(names)}; {filter_label}):"]
        if not names:
            lines.append("<none>")
            return "\n".join(lines)
        current = names[0]
        for name in names[1:]:
            candidate = f"{current}, {name}"
            if len(candidate) > 120:
                lines.append(current)
                current = name
            else:
                current = candidate
        lines.append(current)
        lines.append(
            "Choose a class from this index, then call search(focus_types=[\"ClassName\"]) "
            "for the exact signature before constructing it."
        )
        return "\n".join(lines)

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
        graph_hints = self._format_graph_present_search_miss_hints(focus_types)
        if graph_hints:
            lines.append("")
            lines.append(graph_hints.rstrip())
        lines.append(
            "This only means the current authoring schema does not expose that "
            "class. It does not invalidate workflow precedent or community "
            "evidence. Use available signatures for actual edits; if no "
            "authorable class is available, choose an evidence-supported "
            "available alternative or stop cleanly with clarify(...)."
        )
        return "\n".join(lines) + "\n"

    def _format_focus_type_related_hints(
        self,
        *,
        focus_types: list[str],
        rows: list[NodeSignatureRow],
    ) -> str:
        """Return advisory sibling class names for successful exact lookups."""
        from vibecomfy.porting.emitter import emit_available_node_signatures

        found = {
            row.class_type
            for row in rows
            if isinstance(getattr(row, "class_type", None), str)
        }
        requested = [
            class_type
            for class_type in focus_types
            if isinstance(class_type, str) and class_type in found
        ]
        if not requested:
            return ""
        try:
            all_rows = emit_available_node_signatures(self.schema_provider)
        except Exception:
            return ""
        available = [
            row.class_type
            for row in all_rows
            if isinstance(getattr(row, "class_type", None), str)
        ]
        excluded = set(focus_types)
        lines: list[str] = []
        for class_type in requested:
            related = self._related_class_type_names(class_type, available, excluded=excluded)
            if related:
                lines.append(f"- {class_type}: " + ", ".join(related))
        if not lines:
            return ""
        return (
            "Related available class names (advisory only; call "
            "search(focus_types=[\"ClassName\"]) for any exact signature before use):\n"
            + "\n".join(lines)
            + "\n"
        )

    @staticmethod
    def _related_class_type_names(
        class_type: str,
        available: list[str],
        *,
        excluded: set[str],
        limit: int = 8,
    ) -> list[str]:
        scored: list[tuple[int, str]] = []
        for candidate in available:
            if candidate in excluded or candidate == class_type:
                continue
            score = _class_type_relatedness_score(class_type, candidate)
            if score >= 5:
                scored.append((-score, candidate))
        scored.sort(key=lambda item: (item[0], item[1].casefold(), item[1]))
        return [candidate for _, candidate in scored[:limit]]

    def _format_graph_present_search_miss_hints(self, focus_types: list[str]) -> str:
        present = self._graph_nodes_by_class_type(focus_types)
        if not present:
            return ""
        lines = [
            "Graph context: the missing class is already present in the current graph, "
            "but this edit session has no authoring signature for constructing it."
        ]
        for class_type in sorted(present):
            candidate_lines = self._graph_adjacent_authorable_candidate_lines(
                present[class_type],
            )
            if candidate_lines:
                lines.append(f"Adjacent schema-backed candidates near {class_type}:")
                lines.extend(candidate_lines)
            else:
                lines.append(
                    "No immediate schema-backed upstream/downstream candidates found near "
                    f"{class_type}."
                )
        return "\n".join(lines) + "\n"

    def _graph_nodes_by_class_type(
        self,
        focus_types: list[str],
    ) -> dict[str, list[Mapping[str, Any]]]:
        requested = {
            class_type
            for class_type in focus_types
            if isinstance(class_type, str) and class_type
        }
        if not requested:
            return {}
        result: dict[str, list[Any]] = {}
        workflow = getattr(self, "workflow", None)
        nodes = getattr(workflow, "nodes", None) or {}
        for node in nodes.values() if isinstance(nodes, Mapping) else ():
            class_type = str(getattr(node, "class_type", "") or "")
            if class_type in requested:
                result.setdefault(class_type, []).append(node)
        return result

    def _graph_adjacent_authorable_candidate_lines(
        self,
        nodes: list[Any],
        *,
        limit: int = 6,
    ) -> list[str]:
        from vibecomfy.porting.emitter import (
            emit_available_node_signatures,
            format_signature_rows as fmt_rows,
        )

        try:
            all_rows = emit_available_node_signatures(self.schema_provider)
        except Exception:
            return []
        row_by_class = {row.class_type: row for row in all_rows}
        workflow = getattr(self, "workflow", None)
        nodes_by_id: dict[str, Any] = {}
        if workflow is not None:
            for node in workflow.nodes.values():
                nodes_by_id[str(node.id)] = node
        target_ids = {
            str(getattr(node, "id", "") or "")
            for node in nodes
            if getattr(node, "id", None) is not None
        }
        seen: set[tuple[str, str, str]] = set()
        lines: list[str] = []
        for origin_id, origin_slot, target_id, target_slot in self._graph_link_endpoints():
            if origin_id in target_ids:
                neighbor = nodes_by_id.get(str(target_id)) if target_id is not None else None
                direction = "downstream"
                field = self._port_name_for_node(neighbor, target_slot, kind="inputs")
            elif target_id in target_ids:
                neighbor = nodes_by_id.get(str(origin_id)) if origin_id is not None else None
                direction = "upstream"
                field = self._port_name_for_node(neighbor, origin_slot, kind="outputs")
            else:
                continue
            if neighbor is None:
                continue
            neighbor_class = str(getattr(neighbor, "class_type", "") or "")
            row = row_by_class.get(neighbor_class)
            if row is None:
                continue
            name = self._display_name_for_graph_node(neighbor)
            key = (direction, name, neighbor_class)
            if key in seen:
                continue
            seen.add(key)
            signature = fmt_rows([row]).strip()
            via = f" via {field}" if field else ""
            lines.append(f"- {direction}{via}: {name} ({neighbor_class})")
            if signature:
                lines.append("  " + signature.replace("\n", "\n  "))
            if len(seen) >= limit:
                break
        return lines

    def _graph_link_endpoints(self) -> list[tuple[str | None, str | None, str | None, str | None]]:
        workflow = getattr(self, "workflow", None)
        if workflow is None:
            return []
        result: list[tuple[str | None, str | None, str | None, str | None]] = []
        for edge in getattr(workflow, "edges", ()) or ():
            result.append(
                (
                    str(getattr(edge, "from_node", "") or "") or None,
                    str(getattr(edge, "from_output", "") or "") or None,
                    str(getattr(edge, "to_node", "") or "") or None,
                    str(getattr(edge, "to_input", "") or "") or None,
                )
            )
        return result

    @staticmethod
    def _port_name_for_node(node: Any, raw_port: str | None, *, kind: str) -> str | None:
        if not raw_port:
            return None
        if not str(raw_port).isdigit():
            return raw_port
        metadata = getattr(node, "metadata", None)
        ui = metadata.get("_ui") if isinstance(metadata, Mapping) else None
        slots = ui.get(kind) if isinstance(ui, Mapping) else None
        index = int(raw_port)
        if isinstance(slots, list) and 0 <= index < len(slots):
            slot = slots[index]
            if isinstance(slot, Mapping) and slot.get("name"):
                return str(slot["name"])
        return raw_port

    def _display_name_for_graph_node(self, node: Any) -> str:
        uid = self._uid_for_graph_node(node)
        if uid and uid in self.name_by_uid:
            return self.name_by_uid[uid]
        title = self._ir_node_title(node)
        if title:
            return title
        class_type = str(getattr(node, "class_type", "") or "node")
        node_id = getattr(node, "id", None)
        return f"{class_type}#{node_id}" if node_id is not None else class_type

    @staticmethod
    def _uid_for_graph_node(node: Any) -> str | None:
        uid = getattr(node, "uid", None)
        if isinstance(uid, str) and uid:
            return uid
        if isinstance(node, Mapping):
            properties = node.get("properties")
            if isinstance(properties, Mapping):
                raw = properties.get("vibecomfy_uid")
                if isinstance(raw, str) and raw:
                    return raw
            node_id = node.get("id")
            return str(node_id) if node_id is not None else None
        node_id = getattr(node, "id", None)
        return str(node_id) if node_id is not None else None

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
        """Build a map from output slot index to list of synthetic link ids."""
        result: dict[int, list[int]] = {}
        ir_node = None
        workflow = getattr(self, "workflow", None)
        if workflow is not None and node_id is not None:
            ir_node = workflow.nodes.get(str(node_id))
            if ir_node is None:
                for node in workflow.nodes.values():
                    if str(getattr(node, "id", "")) == str(node_id):
                        ir_node = node
                        break
        if ir_node is None:
            return result
        for index, names in enumerate(self._ir_outgoing_by_port(ir_node).values()):
            if names:
                result[index] = list(range(len(names)))
        return result

    def _ir_node_by_uid(self, uid: str) -> Any | None:
        workflow = getattr(self, "workflow", None)
        if workflow is None:
            return None
        for node in workflow.nodes.values():
            if str(getattr(node, "uid", "") or "") == str(uid):
                return node
        return None

    @staticmethod
    def _pair_float(value: Any) -> tuple[float, float] | None:
        if isinstance(value, (list, tuple)) and len(value) == 2:
            try:
                return (float(value[0]), float(value[1]))
            except (TypeError, ValueError):
                return None
        return None

    @staticmethod
    def _ir_node_title(node: Any) -> str | None:
        metadata = getattr(node, "metadata", None)
        if isinstance(metadata, Mapping):
            title = metadata.get("title")
            if isinstance(title, str) and title:
                return title
            ui = metadata.get("_ui")
            if isinstance(ui, Mapping):
                ui_title = ui.get("title")
                if isinstance(ui_title, str) and ui_title:
                    return ui_title
        return None

    @staticmethod
    def _ir_widget_values(node: Any) -> tuple[Any, ...]:
        # Live IR state is the authority: raw_widgets carries the positional
        # widget values from ingest, while captured metadata["_ui"] is never
        # rewritten by interpret and would report stale values after an edit.
        # raw_widgets precedes node.widgets because schema-hydrated widget
        # fields only hold defaults (the real value often lives in inputs).
        raw = getattr(node, "raw_widgets", None)
        values = getattr(raw, "values", None) if raw is not None else None
        if isinstance(values, list):
            return tuple(values)
        widgets = getattr(node, "widgets", None)
        if isinstance(widgets, Mapping) and widgets:
            return tuple(widgets.values())
        metadata = getattr(node, "metadata", None)
        if isinstance(metadata, Mapping):
            ui = metadata.get("_ui")
            if isinstance(ui, Mapping) and isinstance(ui.get("widgets_values"), list):
                return tuple(ui["widgets_values"])
        return ()

    @staticmethod
    def _ir_node_as_mapping(node: Any) -> dict[str, Any]:
        metadata = getattr(node, "metadata", None)
        ui = metadata.get("_ui") if isinstance(metadata, Mapping) else None
        if isinstance(ui, Mapping):
            payload = dict(ui)
            payload.setdefault("type", getattr(node, "class_type", ""))
            payload.setdefault("class_type", getattr(node, "class_type", ""))
            return payload
        return {
            "id": getattr(node, "id", None),
            "type": getattr(node, "class_type", ""),
            "class_type": getattr(node, "class_type", ""),
        }

    def _ir_incoming_link_ids(self, node: Any) -> dict[str, int]:
        incoming: dict[str, int] = {}
        # Live IR edges are the authority; the captured metadata["_ui"] inputs
        # are never rewritten by interpret and would report stale links.
        workflow = getattr(self, "workflow", None)
        node_id = str(getattr(node, "id", "") or "")
        if workflow is not None and node_id:
            next_id = 1
            for edge in getattr(workflow, "edges", ()) or ():
                if str(getattr(edge, "to_node", "")) == node_id:
                    incoming[str(getattr(edge, "to_input", "") or "")] = next_id
                    next_id += 1
        if incoming:
            return incoming
        metadata = getattr(node, "metadata", None)
        ui = metadata.get("_ui") if isinstance(metadata, Mapping) else None
        if isinstance(ui, Mapping):
            for slot in ui.get("inputs") or []:
                if not isinstance(slot, Mapping):
                    continue
                name = slot.get("name")
                link = slot.get("link")
                if isinstance(name, str) and isinstance(link, (int, float)):
                    incoming[name] = int(link)
        return incoming

    def _ir_outgoing_by_port(self, node: Any) -> dict[str, tuple[str, ...]]:
        outgoing: dict[str, list[str]] = {}
        metadata = getattr(node, "metadata", None)
        ui = metadata.get("_ui") if isinstance(metadata, Mapping) else None
        index_names: list[str] = []
        if isinstance(ui, Mapping):
            for output in ui.get("outputs") or []:
                if isinstance(output, Mapping) and output.get("name"):
                    index_names.append(str(output["name"]))
        workflow = getattr(self, "workflow", None)
        node_id = str(getattr(node, "id", "") or "")
        if workflow is not None and node_id:
            for edge in getattr(workflow, "edges", ()) or ():
                if str(getattr(edge, "from_node", "")) != node_id:
                    continue
                port = str(getattr(edge, "from_output", "") or "")
                if port.isdigit() and int(port) < len(index_names):
                    port = index_names[int(port)]
                outgoing.setdefault(port, []).append(str(getattr(edge, "to_node", "") or ""))
        return {name: tuple(targets) for name, targets in outgoing.items()}

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
        """Resolve a widget value through the compact per-node resolver."""
        value = widget_value_for_field(node, field, schema_provider=self.schema_provider)
        if value is missing_widget_value_sentinel():
            return None
        return value

    def _original_node_mode(self, scope_path: str, uid: str) -> Any:
        """Look up the original mode of a node from the original ledger."""
        node = self.original_ledger.resolve_node(scope_path or "", uid)
        if node is not None:
            return node.get("mode", 0)
        return _UNRESOLVED_OLD_VALUE

    def _original_node_title(self, scope_path: str, uid: str) -> Any:
        """Look up the original title of a node from the original ledger."""
        node = self.original_ledger.resolve_node(scope_path or "", uid)
        if node is not None:
            return node.get("title")
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

    def _link_ref_value(self, source: LinkSourceRef) -> dict[str, Any]:
        slot: Any = source.output_slot
        workflow = getattr(self, "workflow", None)
        if workflow is not None and isinstance(slot, str):
            from vibecomfy.porting.edit._interpret import _ui_output_slot

            for item in workflow.nodes.values():
                if str(getattr(item, "uid", "") or "") == str(source.uid):
                    slot = _ui_output_slot(item, slot)
                    break
        return {
            "scope_path": source.scope_path,
            "uid": source.uid,
            "output_slot": slot,
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
                            # LiteGraph link tuples are
                            # [id, origin_id, origin_slot, target_id, target_slot, type].
                            # l[3] is the target node id, not the source slot.
                            src_slot = l[2]
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


_GENERIC_CLASS_TERMS: frozenset[str] = frozenset(
    {
        "apply",
        "base",
        "class",
        "comfy",
        "condition",
        "conditioning",
        "control",
        "decode",
        "encode",
        "gen",
        "graph",
        "image",
        "input",
        "latent",
        "load",
        "loader",
        "mask",
        "model",
        "node",
        "output",
        "preview",
        "save",
        "sampler",
        "text",
        "video",
        "with",
    }
)


def _class_type_relatedness_score(left: str, right: str) -> int:
    left_cf = left.casefold()
    right_cf = right.casefold()
    left_primary = _class_type_primary_segment(left)
    right_primary = _class_type_primary_segment(right)
    score = 0
    if left_primary and left_primary == right_primary:
        score += 9
    common_prefix = _common_prefix_len(_compact_class_type(left_cf), _compact_class_type(right_cf))
    if common_prefix >= 5:
        score += min(common_prefix, 12)
    left_terms = _class_type_terms(left)
    right_terms = _class_type_terms(right)
    shared = left_terms & right_terms
    score += 3 * len(shared)
    if left_cf in right_cf or right_cf in left_cf:
        score += 4
    return score


def _class_type_primary_segment(class_type: str) -> str | None:
    segments = [
        segment.casefold()
        for segment in re.split(r"[^A-Za-z0-9]+", class_type)
        if len(segment) >= 3
    ]
    if not segments:
        return None
    first = segments[0]
    if first in _GENERIC_CLASS_TERMS:
        return None
    return first


def _class_type_terms(class_type: str) -> set[str]:
    terms: set[str] = set()
    for segment in re.split(r"[^A-Za-z0-9]+", class_type):
        if len(segment) >= 3:
            terms.add(segment.casefold())
        for token in re.findall(
            r"[A-Z]+(?=[A-Z][a-z]|[0-9]|$)|[A-Z]?[a-z]+|[0-9]+",
            segment,
        ):
            if len(token) >= 3:
                terms.add(token.casefold())
    return {term for term in terms if term not in _GENERIC_CLASS_TERMS}


def _compact_class_type(class_type: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", class_type.casefold())


def _common_prefix_len(left: str, right: str) -> int:
    count = 0
    for left_char, right_char in zip(left, right):
        if left_char != right_char:
            break
        count += 1
    return count
