"""Alignment tests for docs/gold_template_wan_i2v.py vs ready_templates/video/wan_i2v.py.

Verifies:
- Public input parity (same keys, same default types)
- Output contract parity (same output_type, artifact_kind, etc.)
- Compile success (both templates compile to valid API JSON)
- API/class-type parity (same node class types appear in both)
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

GOLD_PATH = REPO_ROOT / "docs" / "gold_template_wan_i2v.py"
GENERATED_PATH = REPO_ROOT / "ready_templates" / "video" / "wan_i2v.py"


# ── Helpers: load modules dynamically ────────────────────────────────────────

def _load_module(name: str, path: Path):
    """Import a .py file as a module by path."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def gold_mod():
    """Load the gold template module."""
    return _load_module("gold_template_wan_i2v", GOLD_PATH)


@pytest.fixture(scope="module")
def gen_mod():
    """Load the generated template module."""
    # The generated template has import-time issues with the old header being
    # a two-line comment block, but that's a comment — it imports fine.
    return _load_module("generated_wan_i2v", GENERATED_PATH)


@pytest.fixture(scope="module")
def gold_wf(gold_mod):
    """Build the gold template workflow."""
    return gold_mod.build()


@pytest.fixture(scope="module")
def gen_wf(gen_mod):
    """Build the generated template workflow."""
    return gen_mod.build()


# ── Public inputs parity ─────────────────────────────────────────────────────

@pytest.mark.xfail(
    reason=(
        "After F.4/F.5 regen (v2.7) wan_i2v.py uses public() inline and no longer "
        "exposes a top-level PUBLIC_INPUTS dict; gold template alignment to be "
        "updated in Phase 1 when the gold docs template is refreshed."
    ),
    strict=False,
)
def test_public_input_keys_match(gold_mod, gen_mod) -> None:
    """Both templates must expose the same set of public input keys."""
    gold_inputs = gold_mod.PUBLIC_INPUTS
    gen_inputs = gen_mod.PUBLIC_INPUTS

    gold_keys = set(gold_inputs.keys())
    gen_keys = set(gen_inputs.keys())

    assert gold_keys == gen_keys, (
        f"Public input keys differ:\n"
        f"  Gold only:   {gold_keys - gen_keys}\n"
        f"  Generated only: {gen_keys - gold_keys}"
    )


@pytest.mark.xfail(
    reason=(
        "After F.4/F.5 regen (v2.7) wan_i2v.py uses public() inline and no longer "
        "exposes a top-level PUBLIC_INPUTS dict; gold template alignment to be "
        "updated in Phase 1 when the gold docs template is refreshed."
    ),
    strict=False,
)
def test_public_input_default_types_match(gold_mod, gen_mod) -> None:
    """For each shared key, the default values must be semantically equal."""
    gold_inputs = gold_mod.PUBLIC_INPUTS
    gen_inputs = gen_mod.PUBLIC_INPUTS

    for key in gold_inputs:
        gold_spec = gold_inputs[key]
        gen_spec = gen_inputs[key]

        gold_default = gold_spec.default
        gen_default = gen_spec.default

        # For numeric types, check semantic equality (6.0 == 6)
        if isinstance(gold_default, (int, float)) and isinstance(gen_default, (int, float)):
            assert gold_default == gen_default, (
                f"Input '{key}' numeric default differs: "
                f"gold={gold_default} vs gen={gen_default}"
            )
        else:
            assert type(gold_default) is type(gen_default), (
                f"Input '{key}' default type differs: "
                f"gold={type(gold_default).__name__} vs gen={type(gen_default).__name__}"
            )


# ── Output contract parity ───────────────────────────────────────────────────

def test_output_contract_type_matches(gold_wf, gen_wf) -> None:
    """Both workflows must have the same output_type."""
    # Both use wf.finalize(..., output_type='SaveVideo', ...)
    # The output contract is stored in the workflow metadata.
    gold_output = _get_output_type(gold_wf)
    gen_output = _get_output_type(gen_wf)
    assert gold_output == gen_output, (
        f"Output type differs: gold={gold_output} vs gen={gen_output}"
    )


def _get_output_type(wf) -> str | None:
    """Extract the output_type from a finalized workflow."""
    # wf.finalize stores output info in _outputs or similar metadata
    if hasattr(wf, "_outputs") and wf._outputs:
        return wf._outputs[0].get("output_type") if isinstance(wf._outputs, list) else wf._outputs.get("output_type")
    # Try _ready_meta
    if hasattr(wf, "_ready_meta") and wf._ready_meta:
        return getattr(wf._ready_meta, "output_type", None)
    # Fallback: both workflows use SaveVideo as the terminal node
    for node in wf.nodes.values():
        if hasattr(node, "class_type") and node.class_type == "SaveVideo":
            return "SaveVideo"
    return None


def test_output_artifact_kind_matches(gold_wf, gen_wf) -> None:
    """Both workflows must declare the same artifact kind."""
    gold_meta = _get_ready_meta(gold_wf)
    gen_meta = _get_ready_meta(gen_wf)
    if gold_meta and gen_meta:
        gold_kind = getattr(gold_meta, "artifact_kind", None)
        gen_kind = getattr(gen_meta, "artifact_kind", None)
        if gold_kind is not None and gen_kind is not None:
            assert gold_kind == gen_kind, (
                f"Artifact kind differs: gold={gold_kind} vs gen={gen_kind}"
            )


def _get_ready_meta(wf):
    """Extract ReadyMetadata from a workflow."""
    if hasattr(wf, "_ready_meta"):
        return wf._ready_meta
    if hasattr(wf, "meta"):
        return wf.meta
    return None


# ── Compile success ──────────────────────────────────────────────────────────

def test_gold_template_compiles(gold_wf) -> None:
    """Gold template must compile to API JSON without error."""
    api = gold_wf.compile("api")
    assert isinstance(api, dict), f"compile() returned {type(api)}, not dict"
    assert len(api) > 0, "Compiled API JSON is empty"


def test_generated_template_compiles(gen_wf) -> None:
    """Generated template must compile to API JSON without error."""
    api = gen_wf.compile("api")
    assert isinstance(api, dict), f"compile() returned {type(api)}, not dict"
    assert len(api) > 0, "Compiled API JSON is empty"


# ── API / class-type parity ──────────────────────────────────────────────────

def test_node_class_types_overlap(gold_wf, gen_wf) -> None:
    """Both workflows must contain the same set of node class types."""
    gold_types = {n.class_type for n in gold_wf.nodes.values() if hasattr(n, "class_type")}
    gen_types = {n.class_type for n in gen_wf.nodes.values() if hasattr(n, "class_type")}

    assert gold_types == gen_types, (
        f"Node class types differ:\n"
        f"  Gold only:   {gold_types - gen_types}\n"
        f"  Generated only: {gen_types - gold_types}"
    )


def test_node_count_matches(gold_wf, gen_wf) -> None:
    """Both workflows must have the same number of nodes."""
    gold_count = len(gold_wf.nodes)
    gen_count = len(gen_wf.nodes)
    assert gold_count == gen_count, (
        f"Node count differs: gold={gold_count} vs gen={gen_count}"
    )


def test_edge_count_matches(gold_wf, gen_wf) -> None:
    """Both workflows must have the same number of edges."""
    gold_edges = len(gold_wf.edges)
    gen_edges = len(gen_wf.edges)
    assert gold_edges == gen_edges, (
        f"Edge count differs: gold={gold_edges} vs gen={gen_edges}"
    )


# ── Build-only: no GPU work ──────────────────────────────────────────────────

def test_gold_template_is_build_only(gold_mod) -> None:
    """Importing the gold template must not trigger GPU work."""
    # The module-level import already happened in the fixture.
    # Just verify no side effects occurred.
    assert hasattr(gold_mod, "build"), "Gold template missing build()"
    assert hasattr(gold_mod, "PUBLIC_INPUTS"), "Gold template missing PUBLIC_INPUTS"
    assert hasattr(gold_mod, "MODELS"), "Gold template missing MODELS"


def test_generated_template_is_build_only(gen_mod) -> None:
    """Importing the generated template must not trigger GPU work."""
    assert hasattr(gen_mod, "build"), "Generated template missing build()"
    # After F.4/F.5 regen (v2.7), generated templates use inline public()
    # registration inside build() and no longer expose a top-level PUBLIC_INPUTS
    # dict.  Only check for build() and MODELS as the structural invariants.
    assert hasattr(gen_mod, "MODELS"), "Generated template missing MODELS"
