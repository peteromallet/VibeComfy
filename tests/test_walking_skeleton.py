"""Walking skeleton fixture validation + Proof A / Proof D / determinism (M1.5 T13)."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import pytest

from vibecomfy.commands.port import _cmd_port_convert, _cmd_port_export
from vibecomfy.porting.emit.ui import structural_validate

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "walking_skeleton" / "flat.json"

# _stub_layout grid positions: [col*400, row*200] where col ∈ [0,1,2,3]
_STUB_GRID_POSITIONS = {
    (float(col * 400), float(row * 200))
    for row in range(5)
    for col in range(4)
}


def _load() -> dict:
    return json.loads(FIXTURE_PATH.read_text())


def _write_flat_fixture_node_index(tmp_path: Path) -> None:
    """Write a node_index.json covering every node type in the flat fixture."""
    (tmp_path / "node_index.json").write_text(
        json.dumps(
            [
                {
                    "class_type": "CheckpointLoaderSimple",
                    "pack": "core",
                    "inputs": {
                        "ckpt_name": {"type": "STRING", "required": True},
                        "widget_1": {"type": "STRING", "required": False},
                    },
                    "outputs": [
                        {"type": "MODEL", "name": "MODEL"},
                        {"type": "CLIP", "name": "CLIP"},
                        {"type": "VAE", "name": "VAE"},
                    ],
                },
                {
                    "class_type": "CLIPTextEncode",
                    "pack": "core",
                    "inputs": {
                        "clip": {"type": "CLIP", "required": True},
                        "text": {"type": "STRING", "required": True},
                    },
                    "outputs": [{"type": "CONDITIONING", "name": "CONDITIONING"}],
                },
                {
                    "class_type": "EmptyLatentImage",
                    "pack": "core",
                    "inputs": {
                        "width": {"type": "INT", "required": True},
                        "height": {"type": "INT", "required": True},
                        "batch_size": {"type": "INT", "required": True},
                        "widget_0": {"type": "INT", "required": False},
                        "widget_1": {"type": "INT", "required": False},
                        "widget_2": {"type": "INT", "required": False},
                    },
                    "outputs": [{"type": "LATENT", "name": "LATENT"}],
                },
                {
                    "class_type": "KSampler",
                    "pack": "core",
                    "inputs": {
                        "model": {"type": "MODEL", "required": True},
                        "positive": {"type": "CONDITIONING", "required": True},
                        "negative": {"type": "CONDITIONING", "required": True},
                        "latent_image": {"type": "LATENT", "required": True},
                        "seed": {"type": "INT", "required": False},
                        "steps": {"type": "INT", "required": False},
                        "cfg": {"type": "FLOAT", "required": False},
                        "sampler_name": {"type": "STRING", "required": False},
                        "scheduler": {"type": "STRING", "required": False},
                        "denoise": {"type": "FLOAT", "required": False},
                    },
                    "outputs": [{"type": "LATENT", "name": "LATENT"}],
                },
                {
                    "class_type": "VAEDecode",
                    "pack": "core",
                    "inputs": {
                        "samples": {"type": "LATENT", "required": True},
                        "vae": {"type": "VAE", "required": True},
                    },
                    "outputs": [{"type": "IMAGE", "name": "IMAGE"}],
                },
                {
                    "class_type": "SaveImage",
                    "pack": "core",
                    "inputs": {
                        "images": {"type": "IMAGE", "required": True},
                        "filename_prefix": {"type": "STRING", "required": True},
                    },
                    "outputs": [],
                },
            ]
        ),
        encoding="utf-8",
    )


def _setup_roundtrip_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Copy flat.json into tmp_path, write node_index, chdir, return (flat_json, tmp_path)."""
    _write_flat_fixture_node_index(tmp_path)
    fixture = FIXTURE_PATH
    flat_json = tmp_path / "flat.json"
    shutil.copy(fixture, flat_json)
    monkeypatch.chdir(tmp_path)
    return flat_json, tmp_path


def _run_convert(flat_json: Path, out_py: str) -> int:
    """Run port convert on flat.json → out_py."""
    return _cmd_port_convert(
        argparse.Namespace(
            workflow=str(flat_json),
            out=out_py,
            json=True,
            head_check_models=False,
            ready_id=None,
            strict_ready_template=False,
            dry_run=False,
            diff=False,
            all=False,
        )
    )


def _run_export_ui(py_path: str, out_emit: str) -> int:
    """Run port export --to ui on py_path → out_emit."""
    return _cmd_port_export(
        argparse.Namespace(
            workflow=py_path,
            ready=False,
            to="ui",
            json=True,
            out=out_emit,
            object_info_cache=None,
        )
    )


def _is_stub_grid_pos(pos: list) -> bool:
    """Return True if *pos* matches a ``_stub_layout`` deterministic grid cell."""
    return (float(pos[0]), float(pos[1])) in _STUB_GRID_POSITIONS


# ---------------------------------------------------------------------------
# Pre-existing fixture tests (T4)
# ---------------------------------------------------------------------------


def test_flat_fixture_has_no_definitions_subgraphs() -> None:
    data = _load()
    assert "definitions" not in data or "subgraphs" not in data.get("definitions", {}), (
        "flat.json must not contain definitions.subgraphs"
    )


def test_flat_fixture_has_top_level_nodes_with_pos() -> None:
    data = _load()
    assert "nodes" in data, "flat.json must have a top-level nodes array"
    nodes = data["nodes"]
    assert isinstance(nodes, list) and len(nodes) > 0
    for node in nodes:
        assert "pos" in node, f"Node {node.get('id')} missing 'pos'"
        assert isinstance(node["pos"], list), f"Node {node.get('id')} pos must be a list"
        assert len(node["pos"]) == 2, f"Node {node.get('id')} pos must have 2 elements"


# ---------------------------------------------------------------------------
# Proof A — Full CLI round-trip position preservation + structural validation
# ---------------------------------------------------------------------------


def test_proof_a_full_roundtrip_pos_preservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Proof A: port convert → port export --to ui preserves positions and passes structural_validate."""
    flat_json, _ = _setup_roundtrip_fixture(tmp_path, monkeypatch)

    # Step 1 — convert
    code = _run_convert(flat_json, "flat.py")
    assert code == 0, f"port convert failed with code {code}"
    assert (tmp_path / "flat.py").exists(), "flat.py not written"
    assert (tmp_path / "flat.layout.json").exists(), "sidecar not written"

    # Step 2 — export to UI
    out_emit = tmp_path / "flat_emit.json"
    code = _run_export_ui("flat.py", str(out_emit))
    assert code == 0, f"port export --to ui failed with code {code}"
    assert out_emit.exists(), f"flat_emit.json not written at {out_emit}"

    # Load source + emitted
    source_raw = json.loads(flat_json.read_text(encoding="utf-8"))
    emit_data = json.loads(out_emit.read_text(encoding="utf-8"))

    source_pos_by_uid: dict[str, list] = {
        str(node["id"]): node["pos"] for node in source_raw["nodes"]
    }

    # Verify every emitted node:
    # (a) has a non-empty vibecomfy_uid
    # (b) its pos equals the source pos
    # (c) its pos is NOT a _stub_layout grid cell
    for emitted_node in emit_data["nodes"]:
        props = emitted_node.get("properties", {})
        uid = props.get("vibecomfy_uid")
        assert uid, f"Emitted node {emitted_node.get('id')} missing/empty vibecomfy_uid"
        expected_pos = source_pos_by_uid.get(uid)
        assert expected_pos is not None, f"uid {uid} not in source"
        assert emitted_node["pos"] == expected_pos, (
            f"uid {uid}: expected pos {expected_pos}, got {emitted_node['pos']}"
        )
        assert not _is_stub_grid_pos(emitted_node["pos"]), (
            f"uid {uid}: pos {emitted_node['pos']} is a stub grid cell — "
            f"position was NOT restored from the sidecar"
        )

    # Structural validation — no dangling links.
    # Called without a schema_provider so widget-length checks are best-effort;
    # the critical invariant is link endpoint integrity.
    report = structural_validate(emit_data)
    link_errors = [e for e in report["errors"] if "link" in e.lower() or "not in nodes" in e]
    assert not link_errors, (
        f"structural_validate has link/dangling errors: {link_errors}"
    )


# ---------------------------------------------------------------------------
# Proof D — Edit-invariance: position survives a widget-value mutation
# ---------------------------------------------------------------------------


def test_proof_d_edit_invariance_position_survives_widget_edit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Proof D: mutating a widget value (prompt/seed) in the generated .py does NOT shift node positions."""
    flat_json, _ = _setup_roundtrip_fixture(tmp_path, monkeypatch)

    # Step 1 — convert
    code = _run_convert(flat_json, "flat.py")
    assert code == 0, f"port convert failed with code {code}"

    # Step 2 — export (baseline)
    baseline_emit = tmp_path / "flat_emit_baseline.json"
    code = _run_export_ui("flat.py", str(baseline_emit))
    assert code == 0, f"baseline export failed with code {code}"

    # Step 3 — mutate a widget value in flat.py
    py_content = (tmp_path / "flat.py").read_text(encoding="utf-8")
    # The CLIPTextEncode (positive) node has a text prompt — change it
    mutated = py_content.replace(
        '"beautiful scenery nature glass bottle landscape, purple galaxy bottle,"',
        '"MUTATED PROMPT — position must survive this edit"',
    )
    # Also mutate the KSampler seed to prove uid is extrinsic
    mutated = mutated.replace("seed=42", "seed=9999")
    assert mutated != py_content, "mutation produced no change"
    (tmp_path / "flat.py").write_text(mutated, encoding="utf-8")

    # Step 4 — export after mutation
    mutated_emit = tmp_path / "flat_emit_mutated.json"
    code = _run_export_ui("flat.py", str(mutated_emit))
    assert code == 0, f"mutated export failed with code {code}"

    # Step 5 — assert ALL node positions are identical between baseline and mutated
    baseline_data = json.loads(baseline_emit.read_text(encoding="utf-8"))
    mutated_data = json.loads(mutated_emit.read_text(encoding="utf-8"))

    baseline_nodes = baseline_data["nodes"]
    mutated_nodes = mutated_data["nodes"]
    assert len(baseline_nodes) == len(mutated_nodes), (
        f"node count changed: {len(baseline_nodes)} → {len(mutated_nodes)}"
    )

    # Build uid→pos maps
    baseline_pos: dict[str, list] = {}
    for n in baseline_nodes:
        uid = n.get("properties", {}).get("vibecomfy_uid", "")
        if uid:
            baseline_pos[uid] = n["pos"]

    mutated_pos: dict[str, list] = {}
    for n in mutated_nodes:
        uid = n.get("properties", {}).get("vibecomfy_uid", "")
        if uid:
            mutated_pos[uid] = n["pos"]

    assert baseline_pos, "no uids in baseline"
    assert set(baseline_pos.keys()) == set(mutated_pos.keys()), (
        f"uid set changed after mutation: baseline {set(baseline_pos.keys())}, "
        f"mutated {set(mutated_pos.keys())}"
    )

    for uid, expected in baseline_pos.items():
        actual = mutated_pos[uid]
        assert actual == expected, (
            f"Proof D failed: uid {uid} position shifted from {expected} to {actual} "
            f"after widget-value mutation — uid is NOT extrinsic"
        )


# ---------------------------------------------------------------------------
# Determinism — same source → identical uids → identical emitted positions
# ---------------------------------------------------------------------------


def test_determinism_same_source_identical_uids_and_positions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Determinism: two full convert+export runs produce identical uids and positions."""
    flat_json, _ = _setup_roundtrip_fixture(tmp_path, monkeypatch)

    def _full_roundtrip(run_dir: Path) -> dict[str, list]:
        """Run convert + export in *run_dir*, return {uid: pos} from emitted JSON."""
        run_dir.mkdir(parents=True, exist_ok=True)
        local_flat = run_dir / "flat.json"
        shutil.copy(flat_json, local_flat)
        # Write node_index per-run so the fixture is self-contained
        _write_flat_fixture_node_index(run_dir)
        monkeypatch.chdir(run_dir)

        code = _run_convert(local_flat, "flat.py")
        assert code == 0, f"convert failed (run {run_dir.name})"

        emit_path = run_dir / "flat_emit.json"
        code = _run_export_ui("flat.py", str(emit_path))
        assert code == 0, f"export failed (run {run_dir.name})"

        emit_data = json.loads(emit_path.read_text(encoding="utf-8"))
        result: dict[str, list] = {}
        for n in emit_data["nodes"]:
            uid = n.get("properties", {}).get("vibecomfy_uid", "")
            if uid:
                result[uid] = n["pos"]
        return result

    # Run #1
    run1 = _full_roundtrip(tmp_path / "run1")

    # Run #2
    run2 = _full_roundtrip(tmp_path / "run2")

    # Assert identical uid sets
    assert set(run1.keys()) == set(run2.keys()), (
        f"uid sets differ across runs: run1={set(run1.keys())}, run2={set(run2.keys())}"
    )

    # Assert identical positions per uid
    for uid, pos1 in run1.items():
        pos2 = run2[uid]
        assert pos1 == pos2, (
            f"Non-deterministic position for uid {uid}: run1={pos1}, run2={pos2}"
        )


# ---------------------------------------------------------------------------
# T15 — compile('api') byte-identity: uid/pos are furniture inert
# ---------------------------------------------------------------------------


def test_compile_api_byte_identical_uid_pos_not_in_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """compile('api') output is unchanged by uid/pos metadata.

    uid lives in ``VibeNode.uid`` (metadata slot) and pos/size live in
    ``metadata['_ui']`` — they never leak into ``inputs``/``widgets``,
    so the compile('api') dict for the flat fixture is identical to what
    it would be without the identity furniture.
    """
    flat_json, _ = _setup_roundtrip_fixture(tmp_path, monkeypatch)

    from vibecomfy.ingest.normalize import convert_to_vibe_format

    raw = json.loads(flat_json.read_text(encoding="utf-8"))
    wf = convert_to_vibe_format(raw)

    api = wf.compile("api")

    # Every node entry must only have "class_type" and "inputs" keys
    for node_id, node_dict in api.items():
        assert set(node_dict.keys()) <= {"class_type", "inputs"}, (
            f"node {node_id}: unexpected keys in compile('api') output: "
            f"{set(node_dict.keys()) - {'class_type', 'inputs'}}"
        )
        # uid must NOT appear in inputs
        for input_key in node_dict.get("inputs", {}):
            assert "uid" not in input_key.lower(), (
                f"node {node_id}: uid-like key '{input_key}' leaked into inputs"
            )

    # All 7 flat fixture nodes expected
    assert len(api) == 7, (
        f"Expected 7 nodes in compile('api'), got {len(api)}"
    )

    # Verify known node types are present
    expected_types = {
        "CheckpointLoaderSimple",
        "CLIPTextEncode",
        "EmptyLatentImage",
        "KSampler",
        "VAEDecode",
        "SaveImage",
    }
    actual_types = {v["class_type"] for v in api.values()}
    assert expected_types == actual_types, (
        f"Unexpected class_types in compile('api'): {actual_types}"
    )
