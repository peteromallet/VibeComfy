"""Predicate evaluation for demo_factory oracle.

Evaluates whether a candidate graph matches broken or golden state
at the fault locus.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
import re
from typing import Any, Literal

from vibecomfy.ingest.normalize import door_get_links, door_get_nodes, door_get_widgets_values, door_links
# Sentinel: returned by :func:`_find_additive_witness` when no witness node
# satisfies the additive contract.  Distinct from a valid (string) node id.
_ADDITIVE_WITNESS_MISS: str | None = None

AdditiveMode = Literal["practical", "restore-exact", "multinode"]


class AdditiveWitnessVerdict(str, Enum):
    """Practical grade for one additive witness contract."""

    ACCEPTED = "accepted"
    ALTERNATIVE_REPAIR = "alternative_repair"
    REJECTED = "rejected"


@dataclass(frozen=True)
class AdditiveWitnessGrade:
    """Tiered result for an additive witness search.

    ``accepted`` means the node is correctly typed/wired/structured and its
    widgets are exact or practically equivalent.  ``alternative_repair`` has
    the same hard guarantees but carries meaningful widget differences.
    ``rejected`` means no candidate passed the hard additive contract.
    """

    verdict: AdditiveWitnessVerdict
    node_id: str | None
    widget_equivalence: Literal["exact", "practical", "different"] | None
    reason: str

    @property
    def passed(self) -> bool:
        """Whether the additive feature would work at the predicate locus."""
        return self.verdict is not AdditiveWitnessVerdict.REJECTED


def _normalize_widget_value(value: Any) -> Any:
    """Normalize a widget value for positional comparison.

    Mirrors :func:`vibecomfy.demo_factory.deltas._normalize_widget_value` so the
    additive witness compares widgets the same way the delta deriver does.
    Kept local to avoid an import cycle (deltas imports nothing from here, but
    the contract is self-contained and the duplication is tiny).
    """
    if isinstance(value, (int, float, str, bool, type(None))):
        return value
    if isinstance(value, list):
        return [_normalize_widget_value(v) for v in value]
    if isinstance(value, dict):
        return {k: _normalize_widget_value(v) for k, v in sorted(value.items())}
    return str(value)


def _exact_widgets_equal(actual: list[Any], expected: list[Any]) -> bool:
    """Return the historical positional widget-vector equality result."""
    return len(actual) == len(expected) and all(
        _normalize_widget_value(actual[index])
        == _normalize_widget_value(expected[index])
        for index in range(len(expected))
    )


def _as_decimal(value: Any) -> Decimal | None:
    """Return a finite semantic number, excluding booleans."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float, Decimal)):
        text = str(value)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
    else:
        return None
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def _normalized_string(value: str) -> str:
    """Normalize path separators or ordinary enum spelling."""
    stripped = value.strip()
    if "/" in stripped or "\\" in stripped:
        # Comfy model paths use both separators depending on their provenance.
        return re.sub(r"/+", "/", stripped.replace("\\", "/"))
    # Enum values are commonly emitted with inconsequential case and separator
    # differences (for example ``DPM++-2M`` versus ``dpm++_2m``).
    return re.sub(r"[\s_-]+", "_", stripped.casefold())


def _practical_value_equal(actual: Any, expected: Any) -> bool:
    """Compare widget values using run-preserving normalizations."""
    if isinstance(actual, bool) or isinstance(expected, bool):
        return (
            isinstance(actual, bool)
            and isinstance(expected, bool)
            and actual is expected
        )

    actual_number = _as_decimal(actual)
    expected_number = _as_decimal(expected)
    if actual_number is not None and expected_number is not None:
        return actual_number == expected_number

    if isinstance(actual, str) and isinstance(expected, str):
        return _normalized_string(actual) == _normalized_string(expected)

    if isinstance(actual, list) and isinstance(expected, list):
        return _practical_sequences_equal(actual, expected)

    if isinstance(actual, dict) and isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            _practical_value_equal(actual[key], expected[key])
            for key in actual
        )

    return actual == expected


def _is_elidable_default(value: Any) -> bool:
    """Recognize values commonly materialized only as trailing UI defaults."""
    if value is None or value is False:
        return True
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return value == 0
    if isinstance(value, str):
        return value.strip().casefold() in {"", "default"}
    if isinstance(value, (list, dict)):
        return not value
    return False


def _practical_sequences_equal(actual: list[Any], expected: list[Any]) -> bool:
    """Compare vectors while tolerating elided/materialized UI defaults.

    Dynamic alignment handles a default inserted in either vector and also
    makes the ordering of otherwise trailing defaults irrelevant.
    """
    reachable = {(0, 0)}
    while reachable:
        i, j = reachable.pop()
        if i == len(actual) and j == len(expected):
            return True
        if (
            i < len(actual)
            and j < len(expected)
            and _practical_value_equal(actual[i], expected[j])
        ):
            reachable.add((i + 1, j + 1))
        if i < len(actual) and _is_elidable_default(actual[i]):
            reachable.add((i + 1, j))
        if j < len(expected) and _is_elidable_default(expected[j]):
            reachable.add((i, j + 1))
    return False


def _widget_equivalence(
    actual: list[Any],
    expected: list[Any],
) -> Literal["exact", "practical", "different"]:
    if _exact_widgets_equal(actual, expected):
        return "exact"
    if _practical_sequences_equal(actual, expected):
        return "practical"
    return "different"


def _node_index(graph: dict[str, Any]) -> dict[str, dict[str, Any]] | None:
    """Build a unique node index, or reject duplicate/invalid node ids."""
    result: dict[str, dict[str, Any]] = {}
    for node in door_get_nodes(graph, []):
        if not isinstance(node, dict):
            return None
        node_id = str(node.get("id", ""))
        if not node_id or node_id in result:
            return None
        result[node_id] = node
    return result


def _socket_at(
    node: dict[str, Any],
    field: Literal["inputs", "outputs"],
    slot: str,
) -> dict[str, Any] | None:
    """Resolve a UI socket descriptor when the node materializes descriptors."""
    sockets = node.get(field)
    if not isinstance(sockets, list) or not sockets:
        return None
    try:
        slot_index = int(slot)
    except (TypeError, ValueError):
        return None
    if slot_index < 0 or slot_index >= len(sockets):
        return None
    socket = sockets[slot_index]
    return socket if isinstance(socket, dict) else None


def _socket_types(socket: dict[str, Any] | None) -> set[str]:
    if socket is None:
        return set()
    value = socket.get("type")
    if isinstance(value, list):
        return {str(item) for item in value}
    if value is None:
        return set()
    return {str(value)}


def _types_compatible(
    output_socket: dict[str, Any] | None,
    input_socket: dict[str, Any] | None,
    link_type: Any,
) -> bool:
    """Check materialized socket/link types without inventing missing schema."""
    output_types = _socket_types(output_socket)
    input_types = _socket_types(input_socket)
    declared = str(link_type) if link_type is not None else ""
    wildcards = {"", "*", "ANY"}

    if output_types and input_types:
        concrete_out = output_types - wildcards
        concrete_in = input_types - wildcards
        if concrete_out and concrete_in and concrete_out.isdisjoint(concrete_in):
            return False
    if declared not in wildcards:
        if output_types and declared not in output_types and not (output_types & wildcards):
            return False
        if input_types and declared not in input_types and not (input_types & wildcards):
            return False
    return True


def _expected_incident_edges(
    locus: dict[str, Any],
) -> set[tuple[str, str, str, str]] | None:
    """Return (direction, self_slot, peer, peer_slot) signatures."""
    result: set[tuple[str, str, str, str]] = set()
    for edge in locus.get("edges") or []:
        if not isinstance(edge, dict):
            return None
        if not {"direction", "self_slot", "peer", "peer_slot"} <= edge.keys():
            return None
        direction = edge.get("direction")
        if direction not in {"in", "out"}:
            return None
        signature = (
            direction,
            str(edge.get("self_slot")),
            str(edge.get("peer")),
            str(edge.get("peer_slot")),
        )
        if signature in result:
            return None
        result.add(signature)
    return result or None


def _validate_additive_structure(
    graph: dict[str, Any],
    witness_id: str,
    locus: dict[str, Any],
    *,
    boundary_subset: bool = False,
) -> tuple[bool, str]:
    """Enforce the hard type/wiring/socket-consistency part of the contract."""
    nodes = _node_index(graph)
    if nodes is None:
        return False, "graph has invalid or duplicate node ids"
    witness = nodes.get(witness_id)
    if witness is None:
        return False, "witness node is absent"

    expected = _expected_incident_edges(locus)
    if expected is None:
        return False, "additive contract has no valid intended edge path"

    actual: set[tuple[str, str, str, str]] = set()
    incident_count = 0
    seen_link_ids: set[str] = set()
    for link in door_get_links(graph, []):
        if not isinstance(link, list) or len(link) < 6:
            return False, "graph contains a malformed link"
        link_id, from_node, from_slot, to_node, to_slot, link_type = link[:6]
        link_id_s = str(link_id)
        if link_id_s in seen_link_ids:
            return False, "graph contains duplicate link ids"
        seen_link_ids.add(link_id_s)
        from_id, to_id = str(from_node), str(to_node)
        if from_id not in nodes or to_id not in nodes:
            return False, "graph contains a link with a missing endpoint"
        if witness_id not in {from_id, to_id}:
            continue

        incident_count += 1
        if from_id == witness_id:
            signature = ("out", str(from_slot), to_id, str(to_slot))
        else:
            signature = ("in", str(to_slot), from_id, str(from_slot))
        if signature in actual:
            return False, "witness has duplicate incident links"
        actual.add(signature)

        output_node = nodes[from_id]
        input_node = nodes[to_id]
        output_socket = _socket_at(output_node, "outputs", str(from_slot))
        input_socket = _socket_at(input_node, "inputs", str(to_slot))
        if output_node.get("outputs") and output_socket is None:
            return False, "witness link references a missing output socket"
        if input_node.get("inputs") and input_socket is None:
            return False, "witness link references a missing input socket"
        if not _types_compatible(output_socket, input_socket, link_type):
            return False, "witness link connects incompatible socket types"

        if input_socket is not None and "link" in input_socket:
            if str(input_socket.get("link")) != link_id_s:
                return False, "input socket does not reference its witness link"
        if output_socket is not None and isinstance(door_get_links(output_socket), list):
            if link_id_s not in {str(item) for item in door_links(output_socket)}:
                return False, "output socket does not reference its witness link"

    for input_socket in witness.get("inputs", []):
        if (
            isinstance(input_socket, dict)
            and input_socket.get("required") is True
            and input_socket.get("link") is None
        ):
            return False, "witness has a dangling explicitly-required input"

    structure_matches = expected <= actual if boundary_subset else actual == expected
    if not structure_matches:
        return False, "witness incident edges do not match the intended peers and sockets"
    if boundary_subset:
        return True, "witness has the intended surviving boundary roles and compatible link structure"
    return True, "witness has the intended peers, sockets, and compatible link structure"


def grade_additive_witness(
    graph: dict[str, Any],
    locus: dict[str, Any],
    *,
    mode: AdditiveMode = "practical",
) -> AdditiveWitnessGrade:
    """Grade an additive feature by whether it is correctly wired and runnable.

    The hard contract is node class plus the complete incident-edge role and
    locally materialized socket/link consistency.  Widget differences select a
    tier: exact/practical values are ``accepted``; meaningful values are an
    ``alternative_repair``.  The enclosing :class:`Oracle` remains responsible
    for UI→API conversion, required-input resolution, and output reachability.

    ``restore-exact`` is the subordinate regression mode: only the historical
    exact positional widget vector is accepted.
    """
    if mode not in {"practical", "restore-exact", "multinode"}:
        raise ValueError(f"unknown additive grading mode: {mode!r}")

    node_type = locus.get("node_type")
    if not node_type:
        return AdditiveWitnessGrade(
            AdditiveWitnessVerdict.REJECTED, None, None, "missing intended node type"
        )

    expected_widgets = door_get_widgets_values(locus)
    if not isinstance(expected_widgets, list):
        expected_widgets = []

    best_alternative: AdditiveWitnessGrade | None = None
    rejection_reason = f"no {node_type!r} node satisfied the hard additive contract"
    for node in door_get_nodes(graph, []):
        if not isinstance(node, dict) or node.get("type") != node_type:
            continue
        witness_id = str(node.get("id", ""))
        if not witness_id:
            continue

        structure_ok, structure_reason = _validate_additive_structure(
            graph,
            witness_id,
            locus,
            boundary_subset=mode == "multinode",
        )
        if not structure_ok:
            rejection_reason = structure_reason
            continue

        actual_widgets = door_get_widgets_values(node)
        if not isinstance(actual_widgets, list):
            actual_widgets = []
        equivalence = _widget_equivalence(actual_widgets, expected_widgets)

        if mode == "restore-exact" and equivalence != "exact":
            rejection_reason = "restore-exact requires the historical widget vector"
            continue

        if equivalence in {"exact", "practical"}:
            return AdditiveWitnessGrade(
                AdditiveWitnessVerdict.ACCEPTED,
                witness_id,
                equivalence,
                structure_reason,
            )

        best_alternative = AdditiveWitnessGrade(
            AdditiveWitnessVerdict.ALTERNATIVE_REPAIR,
            witness_id,
            "different",
            "hard additive contract passes; widget values differ meaningfully",
        )

    if best_alternative is not None:
        return best_alternative
    return AdditiveWitnessGrade(
        AdditiveWitnessVerdict.REJECTED, None, None, rejection_reason
    )


def _find_additive_witness(
    graph: dict[str, Any],
    locus: dict[str, Any],
    *,
    mode: AdditiveMode = "practical",
) -> str | None:
    """Return the id of a single candidate node satisfying an additive contract.

    In practical mode both accepted and alternative repairs are witnesses:
    widget differences alone cannot turn a correctly typed, correctly wired,
    runnable additive feature into a product failure.

    Returns the first matching candidate node id (str), or ``None`` if no node
    satisfies the hard contract (or the exact widget contract in
    ``restore-exact`` mode).
    """
    grade = grade_additive_witness(graph, locus, mode=mode)
    return grade.node_id if grade.passed else _ADDITIVE_WITNESS_MISS


def evaluate_predicate(
    graph: dict[str, Any],
    predicate: dict[str, Any],
    *,
    additive_mode: AdditiveMode = "practical",
) -> bool:
    """Evaluate whether a graph matches a predicate.

    Parameters
    ----------
    graph:
        UI graph to evaluate.
    predicate:
        Predicate with locus list describing what to check.
    additive_mode:
        ``practical`` (product default) or ``restore-exact`` for the historical
        exact positional widget-vector regression contract.

    Returns
    -------
    bool
        True if graph matches predicate at all locus items.
    """
    if additive_mode not in {"practical", "restore-exact", "multinode"}:
        raise ValueError(f"unknown additive grading mode: {additive_mode!r}")

    locus = predicate.get("locus", [])
    if not locus:
        # Empty predicate matches everything
        return True

    # Build indexes (str-normalize node ids to match str predicate node_ids)
    nodes = {str(node.get("id", "")): node for node in door_get_nodes(graph, [])}
    links = _build_link_set(graph)

    # Check each locus item
    for item in locus:
        locus_type = item.get("type")

        if locus_type == "node_field":
            # Check that node has expected field value
            node_id = item.get("node_id")
            field = item.get("field")
            expected_value = item.get("value")

            if node_id not in nodes:
                return False

            node = nodes[node_id]
            widgets = node.get("widgets", {})
            actual_value = widgets.get(field)

            if actual_value != expected_value:
                return False

        elif locus_type == "link_present":
            # Check that link exists. When ``from_node_type`` / ``to_node_type``
            # is present (additive restore: the fixer re-adds a removed node
            # under a fresh id), match that endpoint by node TYPE instead of id
            # so a sound re-add at a new id is accepted.
            from_node = item.get("from_node")
            from_slot = item.get("from_slot")
            to_node = item.get("to_node")
            to_slot = item.get("to_slot")
            from_type = item.get("from_node_type")
            to_type = item.get("to_node_type")

            from_ids = _ids_of_type(graph, from_node, from_type)
            to_ids = _ids_of_type(graph, to_node, to_type)

            found = any(
                (fid, str(from_slot), tid, str(to_slot)) in links
                for fid in from_ids
                for tid in to_ids
            )
            if not found:
                return False

        elif locus_type == "link_absent":
            # Check that link does not exist (with the same type-tolerance as
            # link_present for additive restores).
            from_node = item.get("from_node")
            from_slot = item.get("from_slot")
            to_node = item.get("to_node")
            to_slot = item.get("to_slot")
            from_type = item.get("from_node_type")
            to_type = item.get("to_node_type")

            from_ids = _ids_of_type(graph, from_node, from_type)
            to_ids = _ids_of_type(graph, to_node, to_type)

            for fid in from_ids:
                for tid in to_ids:
                    if (fid, str(from_slot), tid, str(to_slot)) in links:
                        return False
            # If no concrete ids resolved for a typed endpoint, fall back to
            # "no link into to_slot" so the predicate is still meaningful.
            if not from_ids or not to_ids:
                for key in links:
                    if key[3] == str(to_slot):
                        return False

        elif locus_type == "node_present":
            # Check that node exists
            node_id = item.get("node_id")
            if node_id not in nodes:
                return False

            # Also check type if provided
            node_type = item.get("node_type")
            if node_type:
                node = nodes[node_id]
                if node.get("type") != node_type:
                    return False

        elif locus_type == "node_absent":
            # Check that node does not exist
            node_id = item.get("node_id")
            if node_id in nodes:
                return False

        elif locus_type == "node_type_present":
            # Check that at least min_count nodes of the specified type exist
            node_type = item.get("node_type")
            min_count = item.get("min_count", 1)

            if not node_type:
                return False

            # Count nodes of the specified type
            count = sum(1 for node in door_get_nodes(graph, []) if node.get("type") == node_type)

            if count < min_count:
                return False

        elif locus_type == "widget_value":
            # Check that node has expected widget value at index
            node_id = item.get("node_id")
            widget_index = item.get("widget_index")
            expected_value = item.get("value")

            if node_id not in nodes:
                return False

            node = nodes[node_id]
            widgets_values = door_get_widgets_values(node, [])

            if not isinstance(widgets_values, list):
                return False

            if widget_index is None or not isinstance(widget_index, int):
                return False

            if widget_index >= len(widgets_values):
                return False

            actual_value = widgets_values[widget_index]

            if actual_value != expected_value:
                return False

        elif locus_type == "additive_witness":
            # Repaired side: at least one candidate node must satisfy the full
            # hard additive contract. Widgets select the product grade tier.
            if _find_additive_witness(graph, item, mode=additive_mode) is None:
                return False

        elif locus_type == "additive_absence":
            # Fault side: the broken graph must have NO witness (clean negation
            # of additive_witness).  A correct re-add → witness found → absence
            # False → fault predicate does not match → gate2 passes.
            if _find_additive_witness(graph, item, mode=additive_mode) is not None:
                return False

    return True


def _build_link_set(graph: dict[str, Any]) -> set[tuple[str, str, str, str]]:
    """Build a set of link tuples (from_node, from_slot, to_node, to_slot)."""
    links = door_get_links(graph, [])
    link_set = set()
    for link in links:
        if not isinstance(link, list) or len(link) < 6:
            continue
        # ComfyUI UI link: [link_id, from_node, from_slot, to_node, to_slot, type]
        _, from_node, from_slot, to_node, to_slot, _ = link[:6]
        link_set.add((str(from_node), str(from_slot), str(to_node), str(to_slot)))
    return link_set


def _ids_of_type(
    graph: dict[str, Any],
    node_id: Any,
    node_type: Any,
) -> list[str]:
    """Return the candidate node ids for a link endpoint.

    If ``node_type`` is given (additive restore: the endpoint is a re-added
    node whose fresh id is unknown), return the ids of ALL nodes of that type.
    Otherwise return the single concrete ``node_id`` (str-normalized).
    """
    if node_type:
        return [
            str(n.get("id", ""))
            for n in door_get_nodes(graph, [])
            if n.get("type") == node_type
        ]
    return [str(node_id)] if node_id is not None else []
