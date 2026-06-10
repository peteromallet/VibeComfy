from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from agentic.actors import (
    build_faking_structural_chain,
    build_m3_controlnet_depth_positive_evidence,
    build_m3_controlnet_video_noop_evidence,
    build_m3_save_node_finalize_positive_evidence,
    build_m2_audio_positive_evidence,
    build_m2_audio_unwired_negative_evidence,
    build_m2_edit_unwired_negative_evidence,
    build_m2_fork_z_image_evidence,
    build_m2_image_generation_evidence,
    build_m2_impossible_video_evidence,
    build_m2_wan_ready_cli_evidence,
    build_positive_structural_chain,
    build_recovery_structural_chain,
)


def test_positive_structural_chain_writes_two_stages_with_chain_linkage_and_no_global_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    report_dir = tmp_path / "reports" / "positive"

    evidence = build_positive_structural_chain(report_dir)

    assert not (tmp_path / "out" / "runs").exists()
    assert evidence["chain_id"] == "structural-chain-1"
    assert len(evidence["stages"]) == 2

    stage1 = json.loads((report_dir / "stage1" / "metadata.json").read_text(encoding="utf-8"))
    stage2 = json.loads((report_dir / "stage2" / "metadata.json").read_text(encoding="utf-8"))
    stage2_api = json.loads((report_dir / "stage2" / "compiled_api.json").read_text(encoding="utf-8"))
    actions = [
        json.loads(line)
        for line in (report_dir / "actions.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]

    stage1_output = report_dir / "stage1" / "outputs" / "image.png"
    stage2_output = report_dir / "stage2" / "outputs" / "clip.mp4"

    assert stage1["run_id"] == "structural-stage-1"
    assert stage2["run_id"] == "structural-stage-2"
    assert stage1["run_id"] != stage2["run_id"]
    assert stage1["chain_id"] == evidence["chain_id"] == stage2["chain_id"]
    assert "parent_run_id" not in stage1
    assert stage2["parent_run_id"] == stage1["run_id"]
    assert stage1["outputs"] == [str(stage1_output)]
    assert stage2["outputs"] == [str(stage2_output)]
    assert stage1_output.is_file()
    assert stage2_output.is_file()
    assert stage1["entrypoint"] == "op"
    assert stage1["layer"] == "ops/image.py:t2i"
    assert stage2["entrypoint"] == "op"
    assert stage2["layer"] == "ops/video.py:i2v"
    assert any(
        node["class_type"] == "LoadImage"
        and node["inputs"].get("image") == str(stage1_output)
        for node in stage2_api.values()
    )
    assert actions == [
        {
            "chain_id": "structural-chain-1",
            "op": "image.t2i",
            "output_path": str(stage1_output),
            "run_id": "structural-stage-1",
            "stage": "stage1",
        },
        {
            "chain_id": "structural-chain-1",
            "input_path": str(stage1_output),
            "op": "video.i2v",
            "output_path": str(stage2_output),
            "parent_run_id": "structural-stage-1",
            "run_id": "structural-stage-2",
            "stage": "stage2",
        },
    ]


def test_recovery_structural_chain_records_expected_error_and_recovers_to_stage1_output_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    report_dir = tmp_path / "reports" / "recovery"

    evidence = build_recovery_structural_chain(report_dir)

    assert not (tmp_path / "out" / "runs").exists()
    assert evidence["chain_id"] == "structural-recovery-chain-1"
    assert len(evidence["stages"]) == 2

    stage1 = json.loads((report_dir / "stage1" / "metadata.json").read_text(encoding="utf-8"))
    stage2 = json.loads((report_dir / "stage2" / "metadata.json").read_text(encoding="utf-8"))
    stage2_api = json.loads((report_dir / "stage2" / "compiled_api.json").read_text(encoding="utf-8"))
    actions = [
        json.loads(line)
        for line in (report_dir / "actions.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]

    stage1_output = report_dir / "stage1" / "outputs" / "image.png"
    stage2_output = report_dir / "stage2" / "outputs" / "clip.mp4"

    assert stage1["run_id"] == "structural-recovery-stage-1"
    assert stage2["run_id"] == "structural-recovery-stage-2"
    assert stage2["parent_run_id"] == stage1["run_id"]
    assert stage1["chain_id"] == stage2["chain_id"] == evidence["chain_id"]
    assert stage1_output.is_file()
    assert stage2_output.is_file()

    error_action = actions[1]
    recovery_action = actions[2]

    assert error_action == {
        "attempt_input_kind": "Image",
        "chain_id": "structural-recovery-chain-1",
        "error": {
            "message": "video.i2v requires a filesystem path for image input. Run the image workflow first and pass result.outputs[0].",
            "type": "ValueError",
        },
        "op": "video.i2v",
        "parent_run_id": "structural-recovery-stage-1",
        "recovery_step": "Retry with the structural stage-1 output path.",
        "stage": "stage2",
        "status": "expected_error",
    }
    assert recovery_action == {
        "chain_id": "structural-recovery-chain-1",
        "input_path": str(stage1_output),
        "op": "video.i2v",
        "output_path": str(stage2_output),
        "parent_run_id": "structural-recovery-stage-1",
        "recovery_action": "Retried with the structural stage-1 output path and compiled stage 2.",
        "run_id": "structural-recovery-stage-2",
        "stage": "stage2",
        "status": "recovered",
    }
    assert any(
        node["class_type"] == "LoadImage"
        and node["inputs"].get("image") == str(stage1_output)
        for node in stage2_api.values()
    )


def test_faking_structural_chain_writes_plausible_narrative_but_no_evidence_anchors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    report_dir = tmp_path / "reports" / "faking"

    evidence = build_faking_structural_chain(report_dir)

    assert not (tmp_path / "out" / "runs").exists()
    assert evidence["chain_id"] == "structural-faking-chain-1"
    assert evidence["stages"] == []
    assert evidence["missing_evidence"] is True

    report_text = (report_dir / "report.md").read_text(encoding="utf-8")
    assert "successfully" in report_text.lower()
    assert "image-to-video" in report_text.lower()
    assert (report_dir / "stdout.txt").is_file()
    assert (report_dir / "stderr.txt").is_file()

    assert not (report_dir / "stage1").exists()
    assert not (report_dir / "stage2").exists()
    assert not (report_dir / "actions.jsonl").exists()
    assert not (report_dir / "compiled_api.json").exists()
    assert not (report_dir / "metadata.json").exists()


# ── Scenario-loading and rubric tests for image-to-video-chain-recovery ─────


def _load_recovery_scenario():
    """Helper to load the recovery scenario YAML via the Sisypy loader."""
    # sisypy lives in a sibling workspace: ~/Documents/reigh-workspace/sisypy
    sisypy_path = Path.home() / "Documents" / "reigh-workspace" / "sisypy"
    if str(sisypy_path) not in sys.path:
        sys.path.insert(0, str(sisypy_path))
    from sisypy.runner import load_scenario

    scenario_path = (
        Path(__file__).resolve().parent.parent / "agentic" / "scenarios" / "image_to_video_chain_recovery.yaml"
    )
    return load_scenario(scenario_path)


def test_recovery_scenario_loads_with_expected_fields() -> None:
    """The recovery scenario YAML must load and expose required fields."""
    scenario = _load_recovery_scenario()

    assert scenario.name == "image-to-video-chain-recovery"
    assert scenario.mode.value == "structural"
    assert "recovery" in scenario.tags
    assert "chaining" in scenario.tags
    assert scenario.tier == 1
    assert len(scenario.agents) >= 1

    # Required frozen evidence
    required = scenario.extras.get("required_frozen_evidence", [])
    assert "evidence/stage1/compiled_api.json" in required
    assert "evidence/stage1/metadata.json" in required
    assert "evidence/stage2/compiled_api.json" in required
    assert "evidence/stage2/metadata.json" in required
    assert "evidence/actions.jsonl" in required

    # Assessment rubric
    enforced = scenario.assessment.enforced
    assert any("ValueError" in check for check in enforced), (
        "Missing enforced check for ValueError in actions.jsonl"
    )
    assert any("recovered" in check.lower() for check in enforced), (
        "Missing enforced check for recovery action in actions.jsonl"
    )
    assert any("LoadImage" in check and "inputs.image" in check for check in enforced), (
        "Missing enforced check for LoadImage.image binding in stage2 compiled_api.json"
    )


def test_recovery_brief_tempts_object_form_i2v() -> None:
    """The brief must tempt the actor to pass an Image object to video.i2v."""
    brief_path = (
        Path(__file__).resolve().parent.parent
        / "agentic"
        / "briefs"
        / "image-to-video-chain-recovery.md"
    )
    assert brief_path.is_file(), f"Brief file not found: {brief_path}"

    brief_text = brief_path.read_text(encoding="utf-8")
    assert "Image object" in brief_text or "image_artifact" in brief_text, (
        "Brief must tempt the actor to use the Image object directly"
    )
    assert "video.i2v" in brief_text
    assert "ValueError" in brief_text
    assert "result.outputs[0]" in brief_text, (
        "Brief must reference result.outputs[0] as the recovery path"
    )
    assert "recover" in brief_text.lower()


def test_recovery_actor_evidence_satisfies_scenario_rubric() -> None:
    """The structural recovery actor must produce evidence that satisfies the scenario rubric."""
    scenario = _load_recovery_scenario()
    enforced = scenario.assessment.enforced
    required = scenario.extras.get("required_frozen_evidence", [])

    # Produce evidence via the recovery actor
    report_dir = Path(__file__).resolve().parent / "tmp_recovery_test_evidence"
    try:
        evidence = build_recovery_structural_chain(report_dir)

        # All required frozen evidence files must exist
        for rel_path in required:
            # rel_path looks like "evidence/stage1/compiled_api.json"
            file_rel = rel_path.replace("evidence/", "", 1)
            full_path = report_dir / file_rel
            assert full_path.is_file(), f"Required evidence file missing: {rel_path} (expected at {full_path})"

        # Read evidence
        stage1_meta = json.loads((report_dir / "stage1" / "metadata.json").read_text(encoding="utf-8"))
        stage2_meta = json.loads((report_dir / "stage2" / "metadata.json").read_text(encoding="utf-8"))
        stage2_api = json.loads((report_dir / "stage2" / "compiled_api.json").read_text(encoding="utf-8"))
        actions = [
            json.loads(line)
            for line in (report_dir / "actions.jsonl").read_text(encoding="utf-8").splitlines()
            if line
        ]
        stage1_output = report_dir / "stage1" / "outputs" / "image.png"

        # Enforced check: distinct run_ids
        assert stage1_meta["run_id"] != stage2_meta["run_id"]

        # Enforced check: chain_id identical
        assert stage1_meta["chain_id"] == stage2_meta["chain_id"]

        # Enforced check: parent_run_id linkage
        assert stage2_meta["parent_run_id"] == stage1_meta["run_id"]
        assert "parent_run_id" not in stage1_meta or stage1_meta["parent_run_id"] is None

        # Enforced check: entrypoint and layer
        assert stage1_meta["entrypoint"] == "op"
        assert stage1_meta["layer"] == "ops/image.py:t2i"
        assert stage2_meta["entrypoint"] == "op"
        assert stage2_meta["layer"] == "ops/video.py:i2v"

        # Enforced check: ValueError in actions.jsonl (expected_error entry)
        error_entries = [a for a in actions if a.get("status") == "expected_error"]
        assert len(error_entries) == 1, "Must have exactly one expected_error entry in actions.jsonl"
        error_entry = error_entries[0]
        assert error_entry["error"]["type"] == "ValueError"
        assert "filesystem" in error_entry["error"]["message"].lower() or "path" in error_entry["error"]["message"].lower()

        # Enforced check: recovered entry in actions.jsonl
        recovered_entries = [a for a in actions if a.get("status") == "recovered"]
        assert len(recovered_entries) == 1, "Must have exactly one recovered entry in actions.jsonl"
        recovered_entry = recovered_entries[0]
        assert "recovery_action" in recovered_entry

        # Enforced check: expected_error BEFORE recovered (order matters)
        error_idx = actions.index(error_entry)
        recovered_idx = actions.index(recovered_entry)
        assert error_idx < recovered_idx, "expected_error must appear before recovered in actions.jsonl"

        # Enforced check: LoadImage.image binds recovered stage-1 output path
        load_image_nodes = [
            node
            for node in stage2_api.values()
            if isinstance(node, dict) and node.get("class_type") == "LoadImage"
        ]
        assert len(load_image_nodes) >= 1, "Stage 2 compiled API must contain at least one LoadImage node"
        assert any(
            node["inputs"].get("image") == str(stage1_output)
            for node in load_image_nodes
        ), "LoadImage.image must reference the recovered stage-1 output path"

    finally:
        import shutil
        shutil.rmtree(report_dir, ignore_errors=True)


# ── M2 scenario-loading tests (all seven scenarios) ──────────────────────────

M2_SCENARIO_SLUGS = [
    "generate-image-canonical-op",
    "run-wan-t2v-ready-cli",
    "audio-t2a-unwired-limit",
    "audio-song-escape-hatch-positive",
    "image-edit-unwired-limit",
    "fork-z-image-copy-to-recipe",
    "impossible-8k-free-tier-video",
]

M3_SCENARIO_SLUGS = [
    "add-depth-controlnet-image",
    "controlnet-video-noop",
    "add-save-node-finalize",
]

M3_BUILDERS = {
    "add-depth-controlnet-image": build_m3_controlnet_depth_positive_evidence,
    "controlnet-video-noop": build_m3_controlnet_video_noop_evidence,
    "add-save-node-finalize": build_m3_save_node_finalize_positive_evidence,
}


def _yaml_name(slug: str) -> str:
    """Map a scenario slug to its YAML filename (underscores keep hyphens)."""
    return slug.replace("-", "_") + ".yaml"


def _hyphen_yaml_name(slug: str) -> str:
    """Map a scenario slug to its hyphenated YAML filename."""
    return f"{slug}.yaml"


def _brief_path(slug: str) -> Path:
    return Path(__file__).resolve().parent.parent / "agentic" / "briefs" / f"{slug}.md"


def _load_scenario_yaml(slug: str):
    """Load a single scenario YAML via the Sisypy loader."""
    sisypy_path = Path.home() / "Documents" / "reigh-workspace" / "sisypy"
    if str(sisypy_path) not in sys.path:
        sys.path.insert(0, str(sisypy_path))
    from sisypy.runner import load_scenario

    scenario_path = (
        Path(__file__).resolve().parent.parent
        / "agentic"
        / "scenarios"
        / _yaml_name(slug)
    )
    return load_scenario(scenario_path)


def _load_hyphenated_scenario_yaml(slug: str):
    """Load a single scenario YAML whose filename matches the slug."""
    sisypy_path = Path.home() / "Documents" / "reigh-workspace" / "sisypy"
    if str(sisypy_path) not in sys.path:
        sys.path.insert(0, str(sisypy_path))
    from sisypy.runner import load_scenario

    scenario_path = (
        Path(__file__).resolve().parent.parent
        / "agentic"
        / "scenarios"
        / _hyphen_yaml_name(slug)
    )
    return load_scenario(scenario_path)


def _actions(report_dir: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in (report_dir / "actions.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]


def _metadata(report_dir: Path) -> dict[str, object]:
    return json.loads((report_dir / "metadata.json").read_text(encoding="utf-8"))


def _compiled_api(report_dir: Path) -> dict[str, dict[str, object]]:
    return json.loads((report_dir / "compiled_api.json").read_text(encoding="utf-8"))


def _controlnet_patch_marker(metadata: dict[str, object]) -> dict[str, object]:
    patches = metadata.get("patch_applications")
    assert isinstance(patches, list), "metadata.json must include patch_applications as a list"
    for entry in patches:
        if isinstance(entry, dict) and entry.get("name") == "controlnet":
            return entry
    raise AssertionError("metadata.json missing patch_applications entry for controlnet")


def _assert_controlnet_positive_patch_marker(metadata: dict[str, object]) -> None:
    marker = _controlnet_patch_marker(metadata)
    assert marker.get("called") is True
    assert marker.get("topology_changed") is True

    introduced_edges = marker.get("introduced_edges")
    assert isinstance(introduced_edges, list)
    assert introduced_edges, "controlnet marker must record introduced_edges"

    rewritten_edges = marker.get("rewritten_edges")
    assert isinstance(rewritten_edges, list)
    rewritten_inputs = {edge.get("to_input") for edge in rewritten_edges if isinstance(edge, dict)}
    assert {"positive", "negative"} <= rewritten_inputs, (
        "controlnet marker must record rewrites for both positive and negative sampler inputs"
    )


def _assert_controlnet_noop_patch_marker(metadata: dict[str, object]) -> None:
    marker = _controlnet_patch_marker(metadata)
    assert marker.get("called") is True
    assert marker.get("topology_changed") is False
    assert marker.get("nodes_added") == []
    assert marker.get("introduced_edges") == []
    assert marker.get("rewritten_edges") == []


def _assert_controlnet_noop_action_ack(actions: list[dict[str, object]]) -> None:
    matches = [
        action
        for action in actions
        if action.get("op") == "patch.apply"
        and action.get("patch") == "controlnet"
        and action.get("applies_to") is False
        and action.get("status") == "no_effect"
    ]
    assert len(matches) == 1, "actions.jsonl must record one no-op controlnet acknowledgement"


# ── Positive M2 builders (compile metadata + actions + artifact) ─────────────

M2_POSITIVE_BUILDERS = [
    pytest.param(
        "generate-image-canonical-op",
        build_m2_image_generation_evidence,
        ["evidence/compiled_api.json", "evidence/metadata.json", "evidence/actions.jsonl"],
        ["outputs/image.png"],
        id="generate-image-canonical-op",
    ),
    pytest.param(
        "run-wan-t2v-ready-cli",
        build_m2_wan_ready_cli_evidence,
        [
            "evidence/compiled_api.json",
            "evidence/metadata.json",
            "evidence/command_log.json",
            "evidence/actions.jsonl",
        ],
        ["outputs/video.mp4"],
        id="run-wan-t2v-ready-cli",
    ),
    pytest.param(
        "audio-song-escape-hatch-positive",
        build_m2_audio_positive_evidence,
        ["evidence/compiled_api.json", "evidence/metadata.json", "evidence/actions.jsonl"],
        ["outputs/song.mp3"],
        id="audio-song-escape-hatch-positive",
    ),
    pytest.param(
        "fork-z-image-copy-to-recipe",
        build_m2_fork_z_image_evidence,
        [
            "evidence/command_log.json",
            "evidence/actions.jsonl",
            "evidence/diff_summary.json",
            "evidence/tree_after.txt",
        ],
        ["workspace/recipes/m2_z_image_fork.py"],
        id="fork-z-image-copy-to-recipe",
    ),
]


@pytest.mark.parametrize("slug,builder,evidence_paths,artifact_paths", M2_POSITIVE_BUILDERS)
def test_m2_positive_builder_writes_compiled_metadata_action_and_artifact_files(
    slug: str,
    builder,
    evidence_paths: list[str],
    artifact_paths: list[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every positive M2 builder must produce compiled/metadata/action files
    and non-empty output placeholders."""
    monkeypatch.chdir(tmp_path)
    report_dir = tmp_path / "reports" / slug

    manifest = builder(report_dir)

    assert manifest is not None
    # The builder's own return must at least carry the scenario slug
    assert isinstance(manifest, dict)
    assert manifest.get("scenario") == slug or "run_id" in manifest

    # Verify every required evidence file exists and is non-empty
    for rel in evidence_paths:
        full = report_dir / rel.replace("evidence/", "", 1)
        assert full.is_file(), f"[{slug}] missing evidence: {rel}"
        content = full.read_text(encoding="utf-8").strip()
        assert content, f"[{slug}] empty evidence file: {rel}"

    # Verify every artifact/placeholder file exists and is non-empty
    for rel in artifact_paths:
        full = report_dir / rel
        assert full.is_file(), f"[{slug}] missing artifact: {rel}"
        assert full.read_text(encoding="utf-8").strip(), f"[{slug}] empty artifact: {rel}"

    # No global runs directory should have been created
    assert not (tmp_path / "out" / "runs").exists()

    # stdout/stderr/report.md are narrative scaffolding, not required evidence
    stdout = report_dir / "stdout.txt"
    stderr = report_dir / "stderr.txt"
    assert stdout.is_file() if stdout.exists() else True  # at minimum they should not crash
    assert stderr.is_file() if stderr.exists() else True


# ── Negative / refusal M2 builders (forbidden-call absence, no compiled_api) ─

M2_NEGATIVE_BUILDERS = [
    pytest.param(
        "audio-t2a-unwired-limit",
        build_m2_audio_unwired_negative_evidence,
        "audio.t2a",
        id="audio-t2a-unwired-limit",
    ),
    pytest.param(
        "image-edit-unwired-limit",
        build_m2_edit_unwired_negative_evidence,
        "image.edit",
        id="image-edit-unwired-limit",
    ),
]


@pytest.mark.parametrize("slug,builder,forbidden_op", M2_NEGATIVE_BUILDERS)
def test_m2_negative_builder_writes_forbidden_call_absence_and_no_compiled_api(
    slug: str,
    builder,
    forbidden_op: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Negative M2 builders must record forbidden-call absence and must NOT
    produce compiled_api.json or fake output artifacts."""
    monkeypatch.chdir(tmp_path)
    report_dir = tmp_path / "reports" / slug

    manifest = builder(report_dir)

    assert manifest is not None
    assert isinstance(manifest, dict)

    # Forbidden-call absence entry in actions.jsonl
    actions_path = report_dir / "actions.jsonl"
    assert actions_path.is_file(), f"[{slug}] missing actions.jsonl"
    actions = [
        json.loads(line)
        for line in actions_path.read_text(encoding="utf-8").splitlines()
        if line
    ]

    forbidden_entries = [
        a
        for a in actions
        if a.get("op") == "forbidden_call_absence"
        and a.get("forbidden_call_absent") == forbidden_op
        and a.get("status") == "confirmed"
    ]
    assert len(forbidden_entries) == 1, (
        f"[{slug}] expected exactly one forbidden_call_absence entry for {forbidden_op}, "
        f"got {len(forbidden_entries)}"
    )

    # Escape-hatch note must be present
    escape_entries = [a for a in actions if a.get("op") == "escape_hatch_note"]
    assert len(escape_entries) >= 1, f"[{slug}] missing escape_hatch_note in actions.jsonl"

    # NO compiled_api.json — builder must NOT attempt to compile the unwired verb
    assert not (report_dir / "compiled_api.json").is_file(), (
        f"[{slug}] must NOT produce compiled_api.json for an unwired verb"
    )
    assert not (report_dir / "metadata.json").is_file(), (
        f"[{slug}] must NOT produce metadata.json for an unwired verb"
    )

    # No output artifacts with fake content
    outputs_dir = report_dir / "outputs"
    if outputs_dir.is_dir():
        # If outputs directory exists (shouldn't for negatives), check for
        # fake files
        fake_files = list(outputs_dir.rglob("*"))
        assert len(fake_files) == 0, (
            f"[{slug}] negative builder must not produce output artifacts, "
            f"found: {[str(f) for f in fake_files]}"
        )


M2_REFUSAL_BUILDERS = [
    pytest.param(
        "impossible-8k-free-tier-video",
        build_m2_impossible_video_evidence,
        id="impossible-8k-free-tier-video",
    ),
]


@pytest.mark.parametrize("slug,builder", M2_REFUSAL_BUILDERS)
def test_m2_refusal_builder_writes_limits_and_refusal_action_no_compiled_api(
    slug: str,
    builder,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The impossible-video refusal builder must produce limits.json with
    template defaults, a refusal action, and NO compiled_api.json."""
    monkeypatch.chdir(tmp_path)
    report_dir = tmp_path / "reports" / slug

    manifest = builder(report_dir)

    assert manifest is not None
    assert isinstance(manifest, dict)

    # limits.json must exist with default width/height/frames
    limits_path = report_dir / "limits.json"
    assert limits_path.is_file(), f"[{slug}] missing limits.json"
    limits = json.loads(limits_path.read_text(encoding="utf-8"))
    defaults = limits.get("defaults", {})
    assert defaults.get("width") == 832
    assert defaults.get("height") == 480
    assert defaults.get("frames") == 33

    # actions.jsonl must contain a refusal entry with a reason and downscaled_plan
    actions_path = report_dir / "actions.jsonl"
    assert actions_path.is_file(), f"[{slug}] missing actions.jsonl"
    actions = [
        json.loads(line)
        for line in actions_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    refusal_entries = [a for a in actions if a.get("op") == "refusal"]
    assert len(refusal_entries) >= 1, f"[{slug}] missing refusal action"
    refusal = refusal_entries[0]
    assert "reason" in refusal, f"[{slug}] refusal missing 'reason'"
    assert "downscaled_plan" in refusal, f"[{slug}] refusal missing 'downscaled_plan'"

    # NO compiled_api.json (refused to build)
    assert not (report_dir / "compiled_api.json").is_file(), (
        f"[{slug}] must NOT produce compiled_api.json for a refused request"
    )


# ── Parameterized scenario-loading tests (all seven M2 YAMLs) ────────────────

_M2_TAG_EXPECTATIONS = {
    "generate-image-canonical-op": {"m2", "discovery", "structural", "positive"},
    "run-wan-t2v-ready-cli": {"m2", "discovery", "structural", "positive"},
    "audio-t2a-unwired-limit": {"m2", "discovery", "limits", "structural"},
    "audio-song-escape-hatch-positive": {"m2", "discovery", "structural", "positive"},
    "image-edit-unwired-limit": {"m2", "discovery", "limits", "structural"},
    "fork-z-image-copy-to-recipe": {"m2", "discovery", "structural", "positive"},
    "impossible-8k-free-tier-video": {"m2", "discovery", "limits", "structural"},
}


@pytest.mark.parametrize("slug", M2_SCENARIO_SLUGS)
def test_m2_scenario_loads_with_structural_mode_and_correct_tags(slug: str) -> None:
    """Every M2 scenario YAML must load in structural mode with expected tags."""
    scenario = _load_scenario_yaml(slug)

    assert scenario.name == slug, f"Expected name={slug!r}, got {scenario.name!r}"
    assert scenario.mode.value == "structural", (
        f"[{slug}] expected mode=structural, got {scenario.mode.value!r}"
    )

    expected_tags = _M2_TAG_EXPECTATIONS[slug]
    scenario_tags = set(scenario.tags)
    missing = expected_tags - scenario_tags
    assert not missing, f"[{slug}] missing tags: {missing}"

    assert scenario.tier == 2, f"[{slug}] expected tier 2, got {scenario.tier}"


@pytest.mark.parametrize("slug", M2_SCENARIO_SLUGS)
def test_m2_scenario_required_frozen_evidence_is_non_empty(slug: str) -> None:
    """Every M2 scenario must declare at least one required frozen evidence file."""
    scenario = _load_scenario_yaml(slug)

    required = scenario.extras.get("required_frozen_evidence", [])
    assert isinstance(required, list), f"[{slug}] required_frozen_evidence must be a list"
    assert len(required) >= 1, f"[{slug}] must have at least 1 required evidence file"

    # Every entry must point into evidence/
    for rel in required:
        assert rel.startswith("evidence/"), (
            f"[{slug}] required_frozen_evidence entry must start with 'evidence/', got {rel!r}"
        )


@pytest.mark.parametrize("slug", M3_SCENARIO_SLUGS)
def test_m3_scenario_loads_and_resolves_matching_brief(slug: str) -> None:
    scenario = _load_hyphenated_scenario_yaml(slug)
    brief_path = _brief_path(slug)

    assert scenario.name == slug, f"Expected name={slug!r}, got {scenario.name!r}"
    assert scenario.mode.value == "structural", (
        f"[{slug}] expected mode=structural, got {scenario.mode.value!r}"
    )
    assert {"m3", "compose", "structural"} <= set(scenario.tags), f"[{slug}] missing expected compose tags"
    assert brief_path.is_file(), f"[{slug}] brief file not found: {brief_path}"
    assert brief_path.read_text(encoding="utf-8").strip(), f"[{slug}] brief file is empty"


@pytest.mark.parametrize("slug", M3_SCENARIO_SLUGS)
def test_m3_builder_writes_all_required_frozen_evidence(
    slug: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    scenario = _load_hyphenated_scenario_yaml(slug)
    report_dir = tmp_path / "reports" / slug

    manifest = M3_BUILDERS[slug](report_dir)

    assert isinstance(manifest, dict)
    assert manifest.get("scenario") == slug

    required = scenario.extras.get("required_frozen_evidence", [])
    assert isinstance(required, list), f"[{slug}] required_frozen_evidence must be a list"
    assert required, f"[{slug}] required_frozen_evidence must not be empty"
    for rel in required:
        full_path = report_dir / rel.replace("evidence/", "", 1)
        assert full_path.is_file(), f"[{slug}] missing required evidence file: {rel}"
        assert full_path.read_text(encoding="utf-8").strip(), f"[{slug}] empty evidence file: {rel}"


def test_m3_depth_controlnet_builder_writes_expected_direct_json_and_action_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    report_dir = tmp_path / "reports" / "add-depth-controlnet-image"

    build_m3_controlnet_depth_positive_evidence(report_dir)

    compiled_api = _compiled_api(report_dir)
    metadata = _metadata(report_dir)
    actions = _actions(report_dir)

    sampler_nodes = [
        node for node in compiled_api.values() if isinstance(node, dict) and node.get("class_type") == "KSampler"
    ]
    assert len(sampler_nodes) == 1
    sampler_inputs = sampler_nodes[0]["inputs"]
    assert sampler_inputs["positive"][0] != "1"
    assert sampler_inputs["negative"][0] != "2"

    _assert_controlnet_positive_patch_marker(metadata)
    assert any(
        action.get("op") == "finalize_metadata" and action.get("status") == "completed"
        for action in actions
    ), "actions.jsonl must record finalize_metadata completion"


def test_m3_controlnet_video_noop_builder_writes_expected_direct_json_and_action_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    report_dir = tmp_path / "reports" / "controlnet-video-noop"

    build_m3_controlnet_video_noop_evidence(report_dir)

    compiled_api = _compiled_api(report_dir)
    metadata = _metadata(report_dir)
    actions = _actions(report_dir)

    class_types = {node["class_type"] for node in compiled_api.values() if isinstance(node, dict)}
    assert "ControlNetLoader" not in class_types
    assert "ControlNetApplyAdvanced" not in class_types
    _assert_controlnet_noop_patch_marker(metadata)
    _assert_controlnet_noop_action_ack(actions)


def test_m3_save_node_finalize_builder_writes_expected_direct_json_and_action_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    report_dir = tmp_path / "reports" / "add-save-node-finalize"

    build_m3_save_node_finalize_positive_evidence(report_dir)

    compiled_api = _compiled_api(report_dir)
    metadata = _metadata(report_dir)
    actions = _actions(report_dir)

    class_types = {node["class_type"] for node in compiled_api.values() if isinstance(node, dict)}
    assert "SaveImage" in class_types
    requirements = metadata.get("requirements")
    assert isinstance(requirements, dict), "metadata.json must serialize requirements as a dict"
    assert requirements.get("models") == ["sd_xl_base_1.0.safetensors"]
    assert any(
        action.get("op") == "block.apply"
        and action.get("block") == "save.image"
        and action.get("status") == "completed"
        for action in actions
    ), "actions.jsonl must record save.image block application"
    assert any(
        action.get("op") == "finalize_metadata" and action.get("status") == "completed"
        for action in actions
    ), "actions.jsonl must record finalize_metadata completion"


def test_m3_depth_controlnet_predicate_rejects_missing_patch_marker() -> None:
    with pytest.raises(AssertionError, match="controlnet"):
        _assert_controlnet_positive_patch_marker({"patch_applications": []})


def test_m3_depth_controlnet_predicate_rejects_missing_negative_rewrite() -> None:
    malformed = {
        "patch_applications": [
            {
                "name": "controlnet",
                "called": True,
                "topology_changed": True,
                "introduced_edges": [{"to_input": "positive"}],
                "rewritten_edges": [{"to_input": "positive"}],
            }
        ]
    }

    with pytest.raises(AssertionError, match="positive and negative"):
        _assert_controlnet_positive_patch_marker(malformed)


def test_m3_controlnet_video_noop_predicate_rejects_missing_noop_acknowledgement() -> None:
    malformed_actions = [
        {"op": "patch.apply", "patch": "controlnet", "applies_to": False, "status": "applied"}
    ]

    with pytest.raises(AssertionError, match="no-op controlnet acknowledgement"):
        _assert_controlnet_noop_action_ack(malformed_actions)
