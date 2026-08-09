"""W-01 — Anti-gaming scanner and perturbation helpers.

Reusable test utilities that reject forbidden manifest/prompt fields and
prove that renumbering source IDs or mutating widgets, filenames, prompts,
and sigma values does not change the projected topology.

Usage::

    from tests._splice_antigaming import (
        FORBIDDEN_TOKENS,
        assert_no_forbidden_fields,
        assert_topology_invariant,
        perturb_source_ids,
        perturb_widgets,
        perturb_filenames,
        perturb_prompts,
        perturb_sigma,
    )
"""

from __future__ import annotations

import copy
import dataclasses
import re
from typing import Any, Callable, Dict, FrozenSet, List, Tuple, Union

import pytest

# ---------------------------------------------------------------------------
# Forbidden-token registry
# ---------------------------------------------------------------------------

FORBIDDEN_TOKENS: Tuple[str, ...] = (
    # Fixture-ancestry breadcrumbs — exist only because demo fixtures are
    # template-derived; production input has none.
    "prior_path",
    "source_template",
    # Golden / fixture ancestry markers and known source / campaign node IDs.
    "bee83462150b",
    "05d07d0df6b7",
    "slice_node_ids",
    # Widget value literals that encode fixture-specific data.
    "[0.5, 0.3]",
    # Path / filename markers — these should never leak into manifests or
    # fixer prompts.
    "ready_templates/",
    "custom_nodes/",
    # Case-specific class lists that would leak forbidden identity.
    "depth_controlnet",
    "ReCamMaster",
)

# Pre-compile the patterns for fast substring scanning.
_FORBIDDEN_PATTERNS: Tuple[re.Pattern[str], ...] = tuple(
    re.compile(re.escape(token)) for token in FORBIDDEN_TOKENS
)

# Structural keys that are known-OK to skip during recursion (they are
# framework boilerplate, not user data).
_SKIP_KEYS: frozenset = frozenset({"__dict__", "__weakref__", "__dataclass_fields__"})


# ---------------------------------------------------------------------------
# Recursive forbidden-field scanner
# ---------------------------------------------------------------------------

def _matches_any_forbidden(text: str) -> bool:
    """Return True if *text* contains any forbidden token substring."""
    return any(pattern.search(text) for pattern in _FORBIDDEN_PATTERNS)


def _walk(obj: object, *, context: str) -> None:
    """Recursively walk *obj* and pytest.fail on the first forbidden match."""
    if obj is None:
        return

    if isinstance(obj, str):
        if _matches_any_forbidden(obj):
            pytest.fail(
                f"{context}: found forbidden token in string {obj!r}"
            )
        return

    if isinstance(obj, (int, float, bool, complex)):
        return

    if isinstance(obj, (bytes, bytearray)):
        decoded = obj.decode("utf-8", errors="replace")
        if _matches_any_forbidden(decoded):
            pytest.fail(
                f"{context}: found forbidden token in bytes {decoded!r}"
            )
        return

    if isinstance(obj, (list, tuple)):
        for idx, item in enumerate(obj):
            _walk(item, context=f"{context}[{idx}]")
        return

    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(key, str) and key in _SKIP_KEYS:
                continue
            _walk(key, context=f"{context}.<key {key!r}>")
            _walk(value, context=f"{context}[{key!r}]")
        return

    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        d = dataclasses.asdict(obj)
        _walk(d, context=f"{context}(dataclass:{type(obj).__name__})")
        return

    # Fallback: try iterating attributes (safe version).
    if hasattr(obj, "__dict__"):
        for attr_name, attr_value in vars(obj).items():
            if attr_name in _SKIP_KEYS:
                continue
            _walk(attr_value, context=f"{context}.{attr_name}")
        return

    # If all else fails, convert to string and scan.
    try:
        as_str = str(obj)
    except Exception:
        return
    _walk(as_str, context=f"{context}(str-converted)")


def assert_no_forbidden_fields(obj: object, *, context: str = "") -> None:
    """Recursively walk *obj* and ``pytest.fail`` if any forbidden token is present.

    Parameters
    ----------
    obj : object
        A dataclass, dict, list, str, or primitive to inspect.
    context : str
        Optional prefix for the failure message (e.g. ``"manifest"``).
    """
    ctx = context or type(obj).__name__
    _walk(obj, context=ctx)


# ---------------------------------------------------------------------------
# Perturbation helpers (operate on copies)
# ---------------------------------------------------------------------------

# Graph type: dict of node-id → node-dict
Graph = Dict[str, Dict[str, Any]]

# Projected topology: frozenset of (class_type,) node entries and
# (from_id, out_slot, to_id, in_slot) edge tuples.
Topology = FrozenSet[Union[Tuple[str], Tuple[str, int, str, int]]]


def _deepcopy_graph(graph: Graph) -> Graph:
    """Return a deep copy of a ComfyUI-style graph dict."""
    return copy.deepcopy(graph)


def perturb_source_ids(graph: Graph) -> Graph:
    """Bijectively renumber every node id and rewrite all internal id-references.

    Returns a new graph dict; does not mutate the original.
    """
    g = _deepcopy_graph(graph)
    old_ids = sorted(g.keys())
    # Bijective renaming: prefix every id with "p_" so it's clearly perturbed.
    mapping = {old: f"p_{old}" for old in old_ids}

    # Build new dict with renamed keys.
    new_g: Graph = {}
    for old_id, node in g.items():
        new_node = copy.deepcopy(node)
        # Rewrite all input references that point to other nodes.
        inputs = new_node.get("inputs", {})
        if isinstance(inputs, dict):
            for iname, ival in inputs.items():
                # Standard ComfyUI link format: [node_id, slot_index]
                if isinstance(ival, list) and len(ival) >= 1 and isinstance(ival[0], str):
                    if ival[0] in mapping:
                        ival[0] = mapping[ival[0]]
        new_g[mapping[old_id]] = new_node

    return new_g


def perturb_widgets(graph: Graph) -> Graph:
    """Mutate every scalar widget value in place (return a copy)."""
    g = _deepcopy_graph(graph)
    for node in g.values():
        wv = node.get("widgets_values")
        if isinstance(wv, list):
            for i in range(len(wv)):
                if isinstance(wv[i], (int, float)):
                    wv[i] = wv[i] + 1
                elif isinstance(wv[i], str):
                    wv[i] = wv[i] + "_perturbed"
    return g


def perturb_filenames(graph: Graph) -> Graph:
    """Mutate every filename-like string field (return a copy)."""
    g = _deepcopy_graph(graph)
    for node in g.values():
        for key in ("filename_prefix", "filename", "file", "image", "video",
                     "audio", "model", "vae_name", "clip_name", "lora_name",
                     "control_net_name", "checkpoint", "unet_name", "clip_name1",
                     "clip_name2", "style_models", "upscale_model"):
            val = node.get("inputs", {}).get(key)
            if isinstance(val, str):
                node["inputs"][key] = val + "_PERTURBED"
        # Also check top-level widget values for filenames.
        wv = node.get("widgets_values")
        if isinstance(wv, list):
            for i in range(len(wv)):
                if isinstance(wv[i], str) and "." in wv[i]:
                    wv[i] = wv[i] + "_PERTURBED"
    return g


def perturb_prompts(graph: Graph) -> Graph:
    """Mutate every prompt-like string field (return a copy)."""
    g = _deepcopy_graph(graph)
    for node in g.values():
        for key in ("text", "prompt", "positive", "negative", "text_p",
                     "text_n", "caption", "description", "string",
                     "guidance", "input_text", "prompt_g", "prompt_l",
                     "text_positive", "text_negative"):
            val = node.get("inputs", {}).get(key)
            if isinstance(val, str):
                node["inputs"][key] = val + " ::PERTURBED PROMPT::"
    return g


def perturb_sigma(graph: Graph) -> Graph:
    """Mutate every sigma / noise-schedule scalar field (return a copy)."""
    g = _deepcopy_graph(graph)
    for node in g.values():
        for key in ("sigma", "sigma_max", "sigma_min", "start_at_step",
                     "end_at_step", "denoise", "noise_seed", "seed",
                     "steps", "cfg", "scheduler", "sampler_name"):
            val = node.get("inputs", {}).get(key)
            if isinstance(val, (int, float)):
                node["inputs"][key] = val + 0.001 if isinstance(val, float) else val + 1
            elif isinstance(val, str):
                node["inputs"][key] = val + "_sigma_perturbed"
    return g


# ---------------------------------------------------------------------------
# Default shallow projector
# ---------------------------------------------------------------------------

def default_project_topology(graph: Graph) -> Topology:
    """Return an **ID-free** frozenset of (class_type,) nodes and
    (from_class, out_slot, to_class, in_slot) edges.

    Ignores all scalar widget values — only structural class types and links
    are captured.  Node IDs are stripped so the projection is invariant under
    source-ID renumbering.
    """
    id_to_class: Dict[str, str] = {}
    for nid, node in graph.items():
        id_to_class[nid] = node.get("class_type", node.get("type", "?"))

    nodes: set = set()
    edges: set = set()

    for nid, node in graph.items():
        ct = id_to_class[nid]
        nodes.add((ct,))
        inputs = node.get("inputs", {})
        if isinstance(inputs, dict):
            for iname, ival in inputs.items():
                if isinstance(ival, list) and len(ival) >= 1 and isinstance(ival[0], str):
                    target_id = ival[0]
                    target_ct = id_to_class.get(target_id, "?")
                    slot = ival[1] if len(ival) >= 2 and isinstance(ival[1], int) else 0
                    edges.add((ct, iname, target_ct, slot))

    return frozenset(nodes | edges)


# ---------------------------------------------------------------------------
# Topology-invariance assertion
# ---------------------------------------------------------------------------

_PERTURBATIONS: List[Tuple[str, Callable[[Graph], Graph]]] = [
    ("perturb_source_ids", perturb_source_ids),
    ("perturb_widgets", perturb_widgets),
    ("perturb_filenames", perturb_filenames),
    ("perturb_prompts", perturb_prompts),
    ("perturb_sigma", perturb_sigma),
]


def assert_topology_invariant(
    project_fn: Callable[[Graph], object],
    graph: Graph,
    *,
    context: str = "",
) -> None:
    """Assert that *project_fn* returns equal results for *graph* and every perturbation of it.

    Parameters
    ----------
    project_fn : Graph → projected-topology
        A pure function that maps a graph dict to a hashable/equatable
        projection.  Default: :func:`default_project_topology`.
    graph : Graph
        The base ComfyUI-style graph dict.
    context : str
        Optional prefix for failure messages.
    """
    base_proj = project_fn(graph)
    prefix = f"{context}: " if context else ""

    for name, perturb_fn in _PERTURBATIONS:
        perturbed = perturb_fn(graph)
        perturbed_proj = project_fn(perturbed)
        assert perturbed_proj == base_proj, (
            f"{prefix}topology changed after {name}:\n"
            f"  base:      {sorted(str(x) for x in base_proj)}\n"
            f"  perturbed: {sorted(str(x) for x in perturbed_proj)}"
        )
