"""B02-C4 — corpus-wide rich-preservation proof tests.

Executes :mod:`scripts.check_b02_rich_preservation` over a tracked mini corpus
of real, migrated serialized-Vibe envelopes and asserts the preservation proof
holds: zero projection mismatches and zero uid-less emissions. The full ignored
corpus is exercised explicitly by ``make b02-corpus-full CORPUS_DIR=...``.

A synthetic rich envelope with nonempty groups and real link/edge topology
proves the groups and semantic link projections survive the pipeline and that
the checker's projections are not vacuous (a corrupted copy is detected).
"""

from __future__ import annotations

import functools
import hashlib
import json
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from scripts import check_b02_rich_preservation as b02
from scripts import migrate_external_workflow_corpus as migrate
from vibecomfy.ingest import from_envelope


MINI_CORPUS = Path(__file__).parent / "fixtures" / "b02_corpus_mini"


# ---------------------------------------------------------------------------
# Corpus-wide proof (module-scoped cache: traverse the corpus exactly once)
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=1)
def _corpus_summary() -> dict[str, Any]:
    return b02.check_corpus(MINI_CORPUS, expected_count=3)


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


def test_mini_corpus_is_first_class_and_execution_is_freshly_derived() -> None:
    envelopes = list(b02.iter_corpus(MINI_CORPUS))
    assert len(envelopes) == 3
    for _path, raw in envelopes:
        assert "compiled_api" not in raw
        assert isinstance(raw["groups"], list)
        assert all(
            isinstance(entry.get("mode"), int) and not isinstance(entry["mode"], bool)
            for entry in raw["nodes"].values()
        )
        # Legacy UI evidence remains in place even though first-class mode is authoritative.
        for entry in raw["nodes"].values():
            ui = entry.get("metadata", {}).get("_ui")
            if isinstance(ui, dict) and "mode" in ui:
                assert ui["mode"] == entry["mode"]
        derived_api = from_envelope(raw).compile("api")
        assert isinstance(derived_api, dict)
        assert derived_api


def test_checker_reports_checked_and_skipped_sidecar_counts() -> None:
    summary = _corpus_summary()
    assert summary["checked"] == 3
    assert summary["skipped"] == 1
    assert summary["skipped_sidecars"] == 1


def test_checker_rejects_missing_and_empty_corpus_dirs(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="does not exist"):
        b02.check_corpus(tmp_path / "missing")
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError, match="zero envelopes"):
        b02.check_corpus(empty)


def test_migrator_rejects_missing_empty_and_explicit_sidecar(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="does not exist"):
        migrate.migrate_corpus(tmp_path / "missing", write=False)
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError, match="zero envelopes"):
        migrate.migrate_corpus(empty, write=False)
    sidecar = MINI_CORPUS / "001cd1f527f7f288.layout.json"
    with pytest.raises(ValueError, match="sidecar cannot be migrated explicitly"):
        migrate.migrate_corpus(sidecar, write=False)
    with pytest.raises(ValueError, match="expected 2797 envelopes, found 3"):
        migrate.migrate_corpus(MINI_CORPUS, write=False, expected_count=2797)


def test_migrator_check_is_idempotent_on_mini_corpus(tmp_path: Path) -> None:
    report_path = tmp_path / "delta.json"
    report = migrate.migrate_corpus(
        MINI_CORPUS,
        write=False,
        report_path=report_path,
        expected_count=3,
    )
    assert report["summary"]["files_would_change"] == 0
    assert report["summary"]["node_modes_after"] == 20
    assert sum(report["summary"]["node_mode_values_after"].values()) == 20
    assert report["summary"]["sidecars_untouched"] == 1
    assert json.loads(report_path.read_text(encoding="utf-8")) == report


def test_migrator_write_preserves_metadata_sidecar_and_is_idempotent(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    shutil.copytree(MINI_CORPUS, corpus)
    envelope_path = corpus / "90a1d5ff9044902e.json"
    raw = json.loads(envelope_path.read_text(encoding="utf-8"))
    metadata_before = deepcopy(raw["metadata"])
    node_metadata_before = {
        node_id: deepcopy(entry["metadata"])
        for node_id, entry in raw["nodes"].items()
    }
    raw.pop("groups")
    for entry in raw["nodes"].values():
        entry.pop("mode")
    raw["compiled_api"] = from_envelope(raw).compile("api")
    envelope_path.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    sidecar = corpus / "001cd1f527f7f288.layout.json"
    sidecar_before = sidecar.read_bytes()

    first = migrate.migrate_corpus(corpus, write=True, report_path=tmp_path / "write.json")
    assert first["summary"]["files_would_change"] == 1
    written = json.loads(envelope_path.read_text(encoding="utf-8"))
    assert "compiled_api" not in written
    assert written["groups"] == []
    assert written["metadata"] == metadata_before
    assert {
        node_id: entry["metadata"] for node_id, entry in written["nodes"].items()
    } == node_metadata_before
    assert all(isinstance(entry["mode"], int) for entry in written["nodes"].values())
    assert sidecar.read_bytes() == sidecar_before

    second = migrate.migrate_corpus(corpus, write=False)
    assert second["summary"]["files_would_change"] == 0


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

    canonical = normalize_agent_edit_graph(_synthetic_envelope()).graph
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


def test_phase0_spike_vibe_envelope_identity_is_frozen() -> None:
    """The rich-envelope spike specimen cannot drift under later law work."""
    path = MINI_CORPUS / "90a1d5ff9044902e.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == (
        "3f7fe8c665328f4ffa8db8f851da2081f288c9e2d107fd697c89de8655cf5f63"
    )
    raw = json.loads(path.read_bytes())
    workflow = from_envelope(raw)
    assert workflow.id == "880d642726389e77"
    assert len(workflow.nodes) == 15
    assert len(workflow.edges) == 10
    assert {node.mode for node in workflow.nodes.values()} == {0, 4}
    assert all(node.uid and isinstance(node.metadata.get("_ui"), dict) for node in workflow.nodes.values())
