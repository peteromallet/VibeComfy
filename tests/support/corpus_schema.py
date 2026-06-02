from __future__ import annotations

from typing import Any

from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec


# ── explicit core schemas ──────────────────────────────────────────────
#
# These override any graph-inferred schemas for the same class_type.
# SetNode / GetNode / Reroute use passthrough semantics: output type is
# inferred from the live links in the graph (or '*' for Reroute).

_EXPLICIT_SCHEMAS: dict[str, NodeSchema] = {
    "SaveImage": NodeSchema(
        class_type="SaveImage",
        pack=None,
        inputs={"images": InputSpec(type="IMAGE", required=True)},
        outputs=[],
    ),
    "SaveVideo": NodeSchema(
        class_type="SaveVideo",
        pack=None,
        inputs={"video": InputSpec(type="VIDEO", required=True)},
        outputs=[],
    ),
    "LoadImage": NodeSchema(
        class_type="LoadImage",
        pack=None,
        inputs={},
        outputs=[
            OutputSpec(type="IMAGE", name="IMAGE"),
            OutputSpec(type="MASK", name="MASK"),
        ],
    ),
    "CLIPTextEncode": NodeSchema(
        class_type="CLIPTextEncode",
        pack=None,
        inputs={
            "clip": InputSpec(type="CLIP", required=True),
            "text": InputSpec(type="STRING", required=True),
        },
        outputs=[OutputSpec(type="CONDITIONING", name="CONDITIONING")],
    ),
    "VAEDecode": NodeSchema(
        class_type="VAEDecode",
        pack=None,
        inputs={
            "samples": InputSpec(type="LATENT", required=True),
            "vae": InputSpec(type="VAE", required=True),
        },
        outputs=[OutputSpec(type="IMAGE", name="IMAGE")],
    ),
    "KSampler": NodeSchema(
        class_type="KSampler",
        pack=None,
        inputs={
            "model": InputSpec(type="MODEL", required=True),
            "positive": InputSpec(type="CONDITIONING", required=True),
            "negative": InputSpec(type="CONDITIONING", required=True),
            "latent_image": InputSpec(type="LATENT", required=True),
            "seed": InputSpec(type="INT"),
            "steps": InputSpec(type="INT"),
            "cfg": InputSpec(type="FLOAT"),
            "sampler_name": InputSpec(type="STRING"),
            "scheduler": InputSpec(type="STRING"),
            "denoise": InputSpec(type="FLOAT"),
        },
        outputs=[OutputSpec(type="LATENT", name="LATENT")],
    ),
    "DualCLIPLoader": NodeSchema(
        class_type="DualCLIPLoader",
        pack=None,
        inputs={
            "clip_name1": InputSpec(type="STRING"),
            "clip_name2": InputSpec(type="STRING"),
        },
        outputs=[OutputSpec(type="CLIP", name="CLIP")],
    ),
    "VAELoader": NodeSchema(
        class_type="VAELoader",
        pack=None,
        inputs={"vae_name": InputSpec(type="STRING")},
        outputs=[OutputSpec(type="VAE", name="VAE")],
    ),
    "SetNode": NodeSchema(
        class_type="SetNode",
        pack=None,
        inputs={"value": InputSpec(type="*")},
        outputs=[OutputSpec(type="*", name="value")],
    ),
    "GetNode": NodeSchema(
        class_type="GetNode",
        pack=None,
        inputs={"value": InputSpec(type="*")},
        outputs=[OutputSpec(type="*", name="value")],
    ),
    "Reroute": NodeSchema(
        class_type="Reroute",
        pack=None,
        inputs={"": InputSpec(type="*")},
        outputs=[OutputSpec(type="*", name="")],
    ),
}

# Types that should have their output type replaced by the inferred
# type from graph links (passthrough semantics).
_PASSTHROUGH_TYPES: frozenset[str] = frozenset({"SetNode", "GetNode"})


def _node_by_id(nodes: list[dict[str, Any]], node_id: int) -> dict[str, Any] | None:
    """Find a node by its integer id in a list of raw UI nodes."""
    for node in nodes:
        if node.get("id") == node_id:
            return node
    return None


def _widget_input_names(node: dict[str, Any]) -> set[str]:
    """Return the set of input names that are widget slots (have a ``widget`` key)."""
    widget_names: set[str] = set()
    for inp in node.get("inputs") or []:
        if isinstance(inp, dict) and "widget" in inp:
            name = inp.get("name")
            if isinstance(name, str):
                widget_names.add(name)
    return widget_names


def _scrape_node_outputs(
    nodes: list[dict[str, Any]],
    out_types: dict[tuple[str, int], str],
) -> None:
    """Record declared output types from every node's ``outputs`` array."""
    for node in nodes:
        class_type = node.get("type")
        if not isinstance(class_type, str):
            continue
        outputs = node.get("outputs") or []
        for slot_index, entry in enumerate(outputs):
            if isinstance(entry, dict):
                otype = entry.get("type")
                if isinstance(otype, str):
                    # Don't overwrite a link-inferred type; link evidence is stronger
                    out_types.setdefault((class_type, slot_index), otype)


def _process_links(
    links: list[Any],
    nodes: list[dict[str, Any]],
    *,
    out_types: dict[tuple[str, int], str],
    in_types_by_name: dict[tuple[str, str], str],
    in_types_by_label: dict[tuple[str, str], str],
) -> None:
    """Process a list of links, populating output and input type lookups.

    Handles both array-format links ``[link_id, origin_id, origin_slot,
    target_id, target_slot, type]`` and dict-format links ``{id, origin_id,
    origin_slot, target_id, target_slot, type}``.
    """
    for link in links:
        if isinstance(link, list):
            # Array format: [link_id, origin_id, origin_slot, target_id, target_slot, type]
            if len(link) < 6:
                continue
            _link_id = link[0]
            origin_id = link[1]
            origin_slot = link[2]
            target_id = link[3]
            target_slot = link[4]
            link_type = link[5]
        elif isinstance(link, dict):
            origin_id = link.get("origin_id")
            origin_slot = link.get("origin_slot")
            target_id = link.get("target_id")
            target_slot = link.get("target_slot")
            link_type = link.get("type")
        else:
            continue

        if not isinstance(origin_id, int) or not isinstance(origin_slot, int):
            continue
        if not isinstance(target_id, int) or not isinstance(target_slot, int):
            continue

        origin_node = _node_by_id(nodes, origin_id)
        target_node = _node_by_id(nodes, target_id)

        # ── record output type (link type overrides declaration) ────
        if origin_node is not None:
            class_type = origin_node.get("type")
            if isinstance(class_type, str) and isinstance(link_type, str):
                out_types[(class_type, origin_slot)] = link_type

        # ── record input type (dual-index by name and label) ────────
        if target_node is not None:
            class_type = target_node.get("type")
            inputs = target_node.get("inputs") or []
            if isinstance(class_type, str) and 0 <= target_slot < len(inputs):
                input_entry = inputs[target_slot]
                if isinstance(input_entry, dict):
                    # Determine the best type: prefer the link's declared type,
                    # then the input entry's own type.
                    effective_type: str | None = None
                    if isinstance(link_type, str):
                        effective_type = link_type
                    else:
                        in_type = input_entry.get("type")
                        if isinstance(in_type, str):
                            effective_type = in_type

                    if effective_type is not None:
                        # Index by name (primary key for most nodes)
                        in_name = input_entry.get("name")
                        if isinstance(in_name, str) and in_name:
                            in_types_by_name[(class_type, in_name)] = effective_type
                        # Index by label (primary key for LTX proxy-widget inputs)
                        in_label = input_entry.get("label")
                        if isinstance(in_label, str) and in_label:
                            in_types_by_label[(class_type, in_label)] = effective_type


def _build_inferred_schema(
    class_type: str,
    out_types: dict[tuple[str, int], str],
    in_types_by_name: dict[tuple[str, str], str],
    in_types_by_label: dict[tuple[str, str], str],
    widget_inputs_by_type: dict[str, set[str]],
    known_input_names: dict[str, set[str]],
    name_to_label: dict[str, dict[str, str]],
) -> NodeSchema | None:
    """Build a minimal NodeSchema from the inferred type lookups.

    Uses *known_input_names* to drive iteration so that each logical
    input slot appears exactly once in the schema.  Name lookups are
    tried first; label lookups are only used as a fallback.
    """

    # ── outputs: collect all (slot_index, type) entries for this class ──
    output_slots: dict[int, str] = {}
    for (ct, slot), otype in out_types.items():
        if ct == class_type:
            output_slots[slot] = otype

    outputs: list[OutputSpec] = []
    if output_slots:
        max_slot = max(output_slots.keys())
        for i in range(max_slot + 1):
            otype = output_slots.get(i, "*")
            outputs.append(OutputSpec(type=otype, name=str(i)))
    else:
        # No output slots recorded — leave outputs empty so callers can
        # detect an outputless node.
        pass

    # ── inputs: collect all (name, type) entries ─────────────────────
    widget_names = widget_inputs_by_type.get(class_type, set())
    known = known_input_names.get(class_type, set())
    nl_map = name_to_label.get(class_type, {})
    input_map: dict[str, str] = {}

    for input_name in sorted(known):
        if input_name in widget_names:
            continue
        # Try name lookup first
        itype = in_types_by_name.get((class_type, input_name))
        if itype is not None:
            input_map[input_name] = itype
            continue
        # Fall back to label lookup using the name→label map
        label = nl_map.get(input_name)
        if label is not None:
            itype = in_types_by_label.get((class_type, label))
            if itype is not None:
                input_map[input_name] = itype
                continue

    # Second pass: add any label-indexed entries that weren't captured
    # by name (e.g. proxy-widget inputs where label is the primary id).
    # Build a set of labels already covered by the name pass.
    covered_labels: set[str] = set()
    for name, label in nl_map.items():
        if name in input_map:
            covered_labels.add(label)
    for (ct, label), itype in in_types_by_label.items():
        if ct == class_type and label not in widget_names and label not in input_map and label not in covered_labels:
            input_map[label] = itype

    # If we have neither outputs nor inputs, return None (skip this type)
    if not outputs and not input_map:
        return None

    inputs = {name: InputSpec(type=itype) for name, itype in input_map.items()}

    return NodeSchema(class_type=class_type, pack=None, inputs=inputs, outputs=outputs)


class GraphInferredSchemaProvider:
    """Schema provider that infers ComfyUI node schemas from graph link evidence."""

    def __init__(
        self,
        out_types: dict[tuple[str, int], str],
        in_types_by_name: dict[tuple[str, str], str],
        in_types_by_label: dict[tuple[str, str], str],
        widget_inputs_by_type: dict[str, set[str]],
        known_input_names: dict[str, set[str]],
        name_to_label: dict[str, dict[str, str]],
    ) -> None:
        self._out_types = out_types
        self._in_types_by_name = in_types_by_name
        self._in_types_by_label = in_types_by_label
        self._widget_inputs_by_type = widget_inputs_by_type
        self._known_input_names = known_input_names
        self._name_to_label = name_to_label
        self._cache: dict[str, NodeSchema | None] = {}

    def get_schema(self, class_type: str) -> NodeSchema | None:
        if class_type in self._cache:
            return self._cache[class_type]

        # 1. Explicit core schema (overrides inference)
        explicit = _EXPLICIT_SCHEMAS.get(class_type)
        if explicit is not None:
            # For passthrough types, replace output type with inferred type
            if class_type in _PASSTHROUGH_TYPES:
                inferred_output_type = self._infer_passthrough_output_type(class_type)
                if inferred_output_type is not None:
                    explicit = NodeSchema(
                        class_type=explicit.class_type,
                        pack=explicit.pack,
                        inputs=explicit.inputs,
                        outputs=[OutputSpec(type=inferred_output_type, name=o.name) for o in explicit.outputs],
                    )
            self._cache[class_type] = explicit
            return explicit

        # 2. Build from inferred types
        schema = _build_inferred_schema(
            class_type,
            self._out_types,
            self._in_types_by_name,
            self._in_types_by_label,
            self._widget_inputs_by_type,
            self._known_input_names,
            self._name_to_label,
        )
        self._cache[class_type] = schema
        return schema

    def _infer_passthrough_output_type(self, class_type: str) -> str | None:
        """Infer the output type of a passthrough node from its outgoing links."""
        # Look at all outgoing edges from this class_type
        for (ct, slot), otype in self._out_types.items():
            if ct == class_type:
                return otype
        # If no outgoing edges recorded, check if we can infer from incoming
        # (for GetNode, output = input type)
        for (ct, name), itype in self._in_types_by_name.items():
            if ct == class_type:
                return itype
        for (ct, label), itype in self._in_types_by_label.items():
            if ct == class_type:
                return itype
        return None


def graph_inferred_schema_provider(raw_ui_json: dict[str, Any]) -> GraphInferredSchemaProvider:
    """Create a schema provider that infers types from a raw ComfyUI workflow JSON.

    Iterates all links in top-level ``links`` and
    ``definitions.subgraphs[*].links``, handling both array-format and
    dict-format links.  Builds lookup tables that map ``(class_type,
    output_slot_index) → socket_type`` for outputs and ``(class_type,
    input_name) → socket_type`` plus ``(class_type, input_label) →
    socket_type`` for inputs (dual-index).

    Returns a :class:`GraphInferredSchemaProvider` whose
    :meth:`~GraphInferredSchemaProvider.get_schema` returns a minimal
    :class:`NodeSchema` with inputs and outputs derived from the graph
    evidence.  Explicit core schemas (SaveImage, SaveVideo, LoadImage,
    CLIPTextEncode, VAEDecode, KSampler, DualCLIPLoader, VAELoader,
    SetNode, GetNode, Reroute) override any inferred schema.
    """
    out_types: dict[tuple[str, int], str] = {}
    in_types_by_name: dict[tuple[str, str], str] = {}
    in_types_by_label: dict[tuple[str, str], str] = {}
    widget_inputs_by_type: dict[str, set[str]] = {}

    # ── collect widget input names + all known input names per class_type ─
    known_input_names: dict[str, set[str]] = {}
    # Map class_type → {input_name: input_label} for disambiguating dual-index lookups.
    name_to_label: dict[str, dict[str, str]] = {}

    def _collect_node_metadata(nodes_list: list[dict[str, Any]]) -> None:
        for node in nodes_list:
            ct = node.get("type")
            if not isinstance(ct, str):
                continue
            widget_names = _widget_input_names(node)
            if widget_names:
                widget_inputs_by_type.setdefault(ct, set()).update(widget_names)
            for inp in node.get("inputs") or []:
                if isinstance(inp, dict):
                    name = inp.get("name")
                    if isinstance(name, str) and name:
                        known_input_names.setdefault(ct, set()).add(name)
                        label = inp.get("label")
                        if isinstance(label, str) and label:
                            name_to_label.setdefault(ct, {})[name] = label

    top_nodes = raw_ui_json.get("nodes") or []
    _collect_node_metadata(top_nodes)
    _scrape_node_outputs(top_nodes, out_types)

    # ── process top-level links (array format) ─────────────────────────
    top_links = raw_ui_json.get("links") or []
    _process_links(
        top_links,
        top_nodes,
        out_types=out_types,
        in_types_by_name=in_types_by_name,
        in_types_by_label=in_types_by_label,
    )

    # ── process subgraph links (dict format) ───────────────────────────
    definitions = raw_ui_json.get("definitions") or {}
    subgraphs = definitions.get("subgraphs") or []
    for subgraph in subgraphs:
        if not isinstance(subgraph, dict):
            continue
        sg_nodes = subgraph.get("nodes") or []
        _collect_node_metadata(sg_nodes)
        _scrape_node_outputs(sg_nodes, out_types)
        sg_links = subgraph.get("links") or []
        _process_links(
            sg_links,
            sg_nodes,
            out_types=out_types,
            in_types_by_name=in_types_by_name,
            in_types_by_label=in_types_by_label,
        )

    return GraphInferredSchemaProvider(
        out_types=out_types,
        in_types_by_name=in_types_by_name,
        in_types_by_label=in_types_by_label,
        widget_inputs_by_type=widget_inputs_by_type,
        known_input_names=known_input_names,
        name_to_label=name_to_label,
    )
