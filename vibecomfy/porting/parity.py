"""Compile-equivalence checker for ready-template conversion.

Lifted from `tools/_compile_equivalence.py` so the converter and the test
can share the same counters. `compile_equivalent(api_a, api_b)` returns
`(True, [])` if both API dicts represent the same workflow modulo node-id
renumbering and ordering, otherwise `(False, [diff_strings])`.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from vibecomfy.testing.canonical import canonical_equal

try:
    from vibecomfy.porting.object_info import class_defaults
except Exception:  # pragma: no cover - object-info availability is environment-dependent
    class_defaults = None  # type: ignore[assignment]


# UI-only node classes the converter strips at IR build. Match the
# stripped set in `tools/format_as_python.py`.
UI_ONLY = frozenset(
    {
        "Note",
        "MarkdownNote",
        "Label (rgthree)",
        "PreviewAny",
        "easy showAnything",
    }
)

CURATED_SCHEMA_DEFAULTS: dict[str, dict[str, Any]] = {
    "UNETLoader": {"weight_dtype": "default"},
    "CLIPLoader": {"device": "default"},
    "KSampler": {"scheduler": "simple", "denoise": 1},
    "KSamplerAdvanced": {"scheduler": "simple"},
    "EmptyLatentImage": {"batch_size": 1},
    "EmptySD3LatentImage": {"batch_size": 1},
    "EmptyFlux2LatentImage": {"batch_size": 1},
    "ImageScale": {"crop": "none"},
    "ImageResizeKJv2": {"crop": "none"},
    "VHS_VideoCombine": {"format": "auto", "codec": "auto"},
    "WanVideoSampler": {"shift": 8},
}


def _is_link(value: Any) -> bool:
    if not (isinstance(value, list) and len(value) == 2):
        return False
    nid, slot = value
    if not isinstance(slot, int):
        return False
    nid_s = str(nid)
    return all(p.isdigit() for p in nid_s.split(":"))


def _is_ui_only(class_type: str) -> bool:
    return class_type in UI_ONLY


def _canonical_key(
    class_type: str,
    key: str,
    *,
    class_widget_aliases: dict[str, list[str | None]] | None = None,
) -> str | None:
    """Translate widget_N -> canonical name when the schema knows it.

    Lets the equality check treat `LoadImage.widget_0='x'` and
    `LoadImage.image='x'` as the same logical input - necessary for
    the converter, which promotes widget_X to canonical names.

    Returns None when the position is a UI-only widget (e.g. KSampler
    `control_after_generate` at index 1) so callers can drop it; both
    sides should normalise the same way to keep equivalence stable.

    When *class_widget_aliases* is provided (a mapping of class_type ->
    ordered widget-only input names from schema-source evidence), it is
    preferred over the static `WIDGET_SCHEMA` table.  This prevents the
    parity comparison from masking incorrect aliases by canonicalising
    both sides through the same (potentially wrong) static table.
    """
    if not key.startswith("widget_"):
        return key
    try:
        idx = int(key.split("_", 1)[1])
    except ValueError:
        return key

    # 1. Schema-source evidence (highest priority - parity guardrail).
    if class_widget_aliases is not None:
        names = class_widget_aliases.get(class_type)
        if names is not None and 0 <= idx < len(names):
            alias = names[idx]
            if alias is not None:
                return alias
            # None entry = UI-only widget, drop it.
            return None

    # 2. Shared resolver fallback. This uses the same provenance ladder as
    # emission/compile so parity cannot drift from production behaviour.
    try:
        from vibecomfy.porting.widgets.aliases import resolve_widget_name_with_provenance
    except Exception:
        return key
    return resolve_widget_name_with_provenance(class_type, idx).name


def class_type_counter(api: dict) -> Counter[str]:
    return Counter(
        node["class_type"]
        for node in api.values()
        if not _is_ui_only(node.get("class_type", ""))
    )


def _is_runtime_ignored_input(key: str, value: Any) -> bool:
    if value is None:
        return True
    if key == "control_after_generate":
        return True
    if key == "add_noise_to_samples" and value == "":
        return True
    if key.startswith("unused_"):
        return True
    if key in {"videopreview", "preview", "preview_image"} and isinstance(value, dict):
        return True
    return False


def _is_schema_default_input(class_type: str, key: str, value: Any) -> bool:
    defaults = dict(CURATED_SCHEMA_DEFAULTS.get(class_type, {}))
    if class_defaults is not None:
        try:
            defaults.update(class_defaults(class_type))
        except Exception:
            pass
    return key in defaults and value == defaults[key]


def widget_value_counter(
    api: dict,
    *,
    class_widget_aliases: dict[str, list[str | None]] | None = None,
) -> Counter[tuple[str, str, str]]:
    values: Counter[tuple[str, str, str]] = Counter()
    for node in api.values():
        class_type = node.get("class_type")
        if _is_ui_only(class_type):
            continue
        seen_for_node: set[tuple[str, str]] = set()
        for key, value in node.get("inputs", {}).items():
            if _is_link(value):
                continue
            canonical = _canonical_key(class_type, key, class_widget_aliases=class_widget_aliases)
            if canonical is None:
                continue  # UI-only widget; drop from both sides for stable equivalence
            if _is_runtime_ignored_input(canonical, value):
                continue
            if _is_schema_default_input(class_type, canonical, value):
                continue
            # Some legacy API fixtures contain both widget_N and the schema
            # alias for the same Comfy input. Generated Python intentionally
            # emits the canonical field once, so equivalence must not count
            # the duplicate legacy representation twice.
            value_repr = repr(value)
            if (canonical, value_repr) in seen_for_node:
                continue
            seen_for_node.add((canonical, value_repr))
            values[(class_type, canonical, value_repr)] += 1
    return values


def topology_counter(
    api: dict,
    *,
    class_widget_aliases: dict[str, list[str | None]] | None = None,
) -> Counter[tuple[str, str, str, int]]:
    topology: Counter[tuple[str, str, str, int]] = Counter()
    for _node_id, node in api.items():
        class_type = node.get("class_type")
        if _is_ui_only(class_type):
            continue
        for key, value in node.get("inputs", {}).items():
            if not _is_link(value):
                continue
            source = api.get(str(value[0]), {})
            source_class = source.get("class_type")
            if _is_ui_only(source_class):
                continue
            canonical = _canonical_key(class_type, key, class_widget_aliases=class_widget_aliases)
            if canonical is None:
                continue  # UI-only widget edge - shouldn't happen in practice but defensive.
            topology[(class_type, canonical, source_class, int(value[1]))] += 1
    return topology


def compile_equivalent(
    api_a: dict,
    api_b: dict,
    *,
    class_widget_aliases: dict[str, list[str | None]] | None = None,
) -> tuple[bool, list[str]]:
    """Compare two compiled API workflows for semantic equivalence.

    The main gate is the shared canonical graph comparator, which ignores
    concrete node ids while preserving class types, literal inputs, topology,
    and collision multiplicity. The older class/widget/topology counters are
    retained only to produce compact supplemental diagnostics on mismatch.

    Returns `(False, diffs)` with one human-readable diff line per
    mismatching counter group when not equivalent.

    When *class_widget_aliases* is provided, widget_N keys on the source
    (`api_a`) side are canonicalised using schema-source evidence rather
    than the static `WIDGET_SCHEMA` table - preventing both sides from
    comparing equal under the same (potentially wrong) alias mapping.
    """
    normalized_a = _canonicalize_api_inputs(api_a, class_widget_aliases=class_widget_aliases)
    normalized_b = _canonicalize_api_inputs(api_b)
    if canonical_equal(normalized_a, normalized_b):
        return True, []

    diffs: list[str] = ["canonical_form mismatch"]
    classes_a, classes_b = class_type_counter(api_a), class_type_counter(api_b)
    if classes_a != classes_b:
        only_a = (classes_a - classes_b)
        only_b = (classes_b - classes_a)
        if only_a:
            diffs.append(f"class_types only in A: {dict(only_a)}")
        if only_b:
            diffs.append(f"class_types only in B: {dict(only_b)}")

    widgets_a = widget_value_counter(api_a, class_widget_aliases=class_widget_aliases)
    widgets_b = widget_value_counter(api_b)
    if widgets_a != widgets_b:
        only_a = (widgets_a - widgets_b)
        only_b = (widgets_b - widgets_a)
        # Cap the diff lines to keep output actionable.
        for key, count in list(only_a.items())[:10]:
            diffs.append(f"widget_value only in A x{count}: {key}")
        for key, count in list(only_b.items())[:10]:
            diffs.append(f"widget_value only in B x{count}: {key}")
        if len(only_a) > 10 or len(only_b) > 10:
            diffs.append(f"... (additional widget_value diffs truncated; +{len(only_a) + len(only_b) - 20})")

    topo_a = topology_counter(api_a, class_widget_aliases=class_widget_aliases)
    topo_b = topology_counter(api_b)
    if topo_a != topo_b:
        only_a = (topo_a - topo_b)
        only_b = (topo_b - topo_a)
        for key, count in list(only_a.items())[:10]:
            diffs.append(f"topology only in A x{count}: {key}")
        for key, count in list(only_b.items())[:10]:
            diffs.append(f"topology only in B x{count}: {key}")
        if len(only_a) > 10 or len(only_b) > 10:
            diffs.append(f"... (additional topology diffs truncated; +{len(only_a) + len(only_b) - 20})")

    return (not diffs, diffs)


def _canonicalize_api_inputs(
    api: dict,
    *,
    class_widget_aliases: dict[str, list[str | None]] | None = None,
) -> dict[str, dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    for node_id, node in sorted(api.items(), key=lambda item: str(item[0])):
        class_type = node.get("class_type", "")
        if _is_ui_only(class_type):
            continue
        inputs: dict[str, Any] = {}
        seen_literals: set[tuple[str, str]] = set()
        for key, value in sorted(node.get("inputs", {}).items()):
            canonical = _canonical_key(class_type, key, class_widget_aliases=class_widget_aliases)
            if canonical is None:
                continue
            if _is_runtime_ignored_input(canonical, value):
                continue
            if _is_schema_default_input(class_type, canonical, value):
                continue
            if not _is_link(value):
                value_repr = repr(value)
                if (canonical, value_repr) in seen_literals:
                    continue
                seen_literals.add((canonical, value_repr))
            inputs[canonical] = value
        normalized[str(node_id)] = {"class_type": class_type, "inputs": inputs}
    return normalized


__all__ = [
    "compile_equivalent",
    "class_type_counter",
    "widget_value_counter",
    "topology_counter",
]
