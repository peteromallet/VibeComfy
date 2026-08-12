"""B02-C4 — corpus-wide rich-preservation proof tests.

Executes :mod:`scripts.check_b02_rich_preservation` over the ENTIRE
``external_workflows/corpus`` (every serialized-Vibe envelope) and asserts the
preservation proof holds: zero projection mismatches and zero uid-less
emissions.  The corpus is traversed exactly once per test session via
module-scoped caching.  No environment-variable skip: the proof either holds or
it fails with a precise per-file/per-axis report.

A synthetic rich envelope with nonempty groups and real link/edge topology
proves the groups and semantic link projections survive the pipeline and that
the checker's projections are not vacuous (a corrupted copy is detected).
"""

from __future__ import annotations

import functools
from copy import deepcopy
from typing import Any

import pytest

from scripts import check_b02_rich_preservation as b02


# ---------------------------------------------------------------------------
# Corpus-wide proof (module-scoped cache: traverse the corpus exactly once)
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=1)
def _corpus_summary() -> dict[str, Any]:
    return b02.check_corpus()


def _failure_digest(summary: dict[str, Any], limit: int = 25) -> str:
    by_axis = ", ".join(
        f"{axis}={count}"
        for axis, count in sorted(summary["mismatches_by_axis"].items())
    )
    rows = "\n".join(
        f"  {row[0]} [{row[1]}] node={row[2]}: expected {row[3]!r} got {row[4]!r}"
        for row in summary["mismatch_rows"][:limit]
    )
    more = (
        f"\n  ... and {len(summary['mismatch_rows']) - limit} more"
        if len(summary["mismatch_rows"]) > limit
        else ""
    )
    return (
        f"workflows={summary['workflows']} "
        f"mismatches={summary['mismatch_count']} ({by_axis}) "
        f"uidless={summary['uidless']} refused_files={len(summary['refused_files'])}\n"
        f"{rows}{more}"
    )


@pytest.mark.timeout(900)
def test_corpus_rich_preservation_zero_mismatches() -> None:
    """The entire corpus round-trips rich→IR→canonical→re-ingest→re-emit with
    zero projection mismatches on every asserted axis."""
    summary = _corpus_summary()
    assert summary["mismatch_count"] == 0, _failure_digest(summary)


@pytest.mark.timeout(900)
def test_corpus_zero_uidless_emissions() -> None:
    """No emitted canonical node may carry a blank/missing properties.vibecomfy_uid."""
    summary = _corpus_summary()
    assert summary["uidless"] == 0, _failure_digest(summary)


# ---------------------------------------------------------------------------
# Synthetic envelope — non-vacuous projection proof
# ---------------------------------------------------------------------------


def _raw_ui_node(
    node_id: int,
    class_type: str,
    *,
    widgets_values: list[Any],
    inputs: list[dict[str, Any]],
    outputs: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": class_type,
        "pos": [0.0, 0.0],
        "size": [300.0, 100.0],
        "flags": {},
        "order": node_id - 1,
        "mode": 4,
        "inputs": inputs,
        "outputs": outputs,
        "properties": {"Node name for S&R": class_type},
        "widgets_values": widgets_values,
    }


def _synthetic_envelope() -> dict[str, Any]:
    """A small but complete serialized-Vibe envelope: 3 nodes, 2 edges, 2 groups.

    Node ids/edges deliberately mirror a real graph (LoadImage → KSampler →
    VAEDecode) with nonempty widgets_values and full raw ``_ui`` payloads so the
    canonicalization exercises the pin path, link renumbering, and groups
    carry-forward.
    """
    return {
        "id": "synthetic-1",
        "vibecomfy_format_version": "1.0",
        "source": {"id": "synthetic-1", "path": None, "source_type": "api", "provenance": {}},
        "metadata": {"external_workflow": False},
        "requirements": {
            "models": [],
            "custom_nodes": [],
            "missing_models": [],
            "missing_nodes": [],
            "unsupported": [],
        },
        "strict_types": False,
        "inputs": {},
        "outputs": [
            {
                "node_id": "3",
                "output_type": "VAEDecode",
                "name": "IMAGE",
                "artifact_kind": "image",
            }
        ],
        "nodes": {
            "1": {
                "id": "1",
                "class_type": "LoadImage",
                "uid": "uid-1",
                "pack": None,
                "inputs": {},
                "widgets": {},
                "raw_widgets": {
                    "values": ["img.png", "image"],
                    "shape": "list",
                    "source": "ui.widgets_values",
                    "has_dict_rows": False,
                    "length": 2,
                },
                "metadata": {
                    "_ui": _raw_ui_node(
                        1,
                        "LoadImage",
                        widgets_values=["img.png", "image"],
                        inputs=[],
                        outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [999], "slot_index": 0}],
                    )
                },
            },
            "2": {
                "id": "2",
                "class_type": "KSampler",
                "uid": "uid-2",
                "pack": None,
                "inputs": {},
                "widgets": {},
                "raw_widgets": {
                    "values": [42, "fixed", 20, 8, 1, "randomize"],
                    "shape": "list",
                    "source": "ui.widgets_values",
                    "has_dict_rows": False,
                    "length": 6,
                },
                "metadata": {
                    "_ui": _raw_ui_node(
                        2,
                        "KSampler",
                        widgets_values=[42, "fixed", 20, 8, 1, "randomize"],
                        inputs=[{"name": "model", "type": "MODEL", "link": 999}],
                        outputs=[{"name": "LATENT", "type": "LATENT", "links": [998], "slot_index": 0}],
                    )
                },
            },
            "3": {
                "id": "3",
                "class_type": "VAEDecode",
                "uid": "uid-3",
                "pack": None,
                "inputs": {},
                "widgets": {},
                "raw_widgets": {
                    "values": [],
                    "shape": "list",
                    "source": "ui.widgets_values",
                    "has_dict_rows": False,
                    "length": 0,
                },
                "metadata": {
                    "_ui": _raw_ui_node(
                        3,
                        "VAEDecode",
                        widgets_values=[],
                        inputs=[{"name": "samples", "type": "LATENT", "link": 998}],
                        outputs=[{"name": "IMAGE", "type": "IMAGE", "links": [], "slot_index": 0}],
                    )
                },
            },
        },
        "edges": [
            {"from_node": "1", "from_output": "0", "to_node": "2", "to_input": "model"},
            {"from_node": "2", "from_output": "0", "to_node": "3", "to_input": "samples"},
        ],
        "groups": [
            {"title": "input-group", "nodes": [1, 2], "color": "#3f789e"},
            {"title": "decode-group", "nodes": [3], "color": "#2c536b"},
        ],
    }


def test_synthetic_envelope_groups_and_link_topology_survive() -> None:
    """The checker's projections are exercised by real (nonempty) data: groups
    and semantic link topology survive canonicalization and re-emission."""
    result = b02.check_envelope(_synthetic_envelope())
    assert result["mismatches"] == [], result["mismatches"]

    assert result["rich_nodes"] == 3
    assert result["rich_edges"] == 2
    assert result["canonical_nodes"] == 3
    assert result["canonical_links"] == 2
    assert result["groups"] == 2
    assert result["pin_opaque"] == 3, "all three schema-less full-payload nodes must pin"
    assert result["uidless"] == 0

    # Groups survive verbatim into the canonical projection (the checker's
    # groups axis is only meaningful because nonempty groups exist here).
    from vibecomfy.comfy_nodes.agent.graph_normalization import normalize_agent_edit_graph

    canonical = normalize_agent_edit_graph(_synthetic_envelope())
    assert canonical["groups"] == _synthetic_envelope()["groups"]

    # Link endpoint+slot topology is asserted exactly: (from, from_slot, to, to_slot).
    assert b02.canonical_link_topology(canonical) == {(1, 0, 2, 0), (2, 0, 3, 0)}


def test_synthetic_projection_detects_corruption() -> None:
    """Projection helpers are not vacuous: a dropped edge set compares unequal.

    ``check_envelope`` is a self-comparison (source vs its own decode/emit).
    A lossless decoder will faithfully round-trip a truncated edge list, so
    the non-vacuous check is that the edge projection distinguishes the
    truncated set from the intact one.
    """
    intact = _synthetic_envelope()
    truncated = deepcopy(intact)
    truncated["edges"] = [
        {"from_node": "1", "from_output": "0", "to_node": "2", "to_input": "model"}
    ]
    assert b02.rich_edge_tuples(truncated) != b02.rich_edge_tuples(intact)
    assert b02.check_envelope(intact)["mismatches"] == []
