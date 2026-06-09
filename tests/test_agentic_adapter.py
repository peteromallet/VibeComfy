from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentic.adapter import VibeComfyProjectAdapter

sisypy = pytest.importorskip("sisypy")


def _scenario(name: str = "image to video") -> sisypy.Scenario:
    return sisypy.Scenario(name=name)


def _run(**extras) -> sisypy.ActorRun:
    run = sisypy.ActorRun(id="run-1", scenario_name="image to video", agent_id="agent-1", tag="tag-1")
    run.extras.update(extras)
    return run


def test_prime_cleans_only_active_workspace(tmp_path: Path) -> None:
    adapter = VibeComfyProjectAdapter(name="vibecomfy", repo_root=tmp_path)
    scenario = _scenario()
    active = tmp_path / "out" / "agentic" / "workspaces" / "image-to-video"
    sibling = tmp_path / "out" / "agentic" / "workspaces" / "other"
    active.mkdir(parents=True)
    sibling.mkdir(parents=True)
    (active / "stale.txt").write_text("stale", encoding="utf-8")
    (sibling / "keep.txt").write_text("keep", encoding="utf-8")

    primed = adapter.prime(scenario)

    assert primed["workspace_dir"] == str(active)
    assert active.is_dir()
    assert list(active.iterdir()) == []
    assert (sibling / "keep.txt").read_text(encoding="utf-8") == "keep"


def test_build_env_strips_runtime_credentials(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    adapter = VibeComfyProjectAdapter(name="vibecomfy", repo_root=tmp_path)
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setenv("PYTHONPATH", "/repo")
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("RUNPOD_API_KEY", "secret")

    env = adapter.build_env(_scenario(), _run())

    assert env["PATH"] == "/usr/bin"
    assert env["PYTHONPATH"] == "/repo"
    assert "OPENAI_API_KEY" not in env
    assert "RUNPOD_API_KEY" not in env


def test_capture_freezes_declared_files_and_json_only_inside_active_evidence_dir(tmp_path: Path) -> None:
    adapter = VibeComfyProjectAdapter(name="vibecomfy", repo_root=tmp_path)
    source = tmp_path / "source.json"
    source.write_text('{"ok": true}', encoding="utf-8")
    evidence_dir = tmp_path / "reports" / "case-1"
    evidence_dir.mkdir(parents=True)
    unrelated = tmp_path / "reports" / "case-2"
    unrelated.mkdir(parents=True)
    (unrelated / "keep.txt").write_text("keep", encoding="utf-8")

    adapter.capture(
        _scenario(),
        _run(
            freeze_files={"compiled_prompt.json": str(source)},
            freeze_json={"metadata.json": {"entrypoint": "op", "layer": "ops/image.py:t2i"}},
        ),
        evidence_dir,
    )

    assert json.loads((evidence_dir / "compiled_prompt.json").read_text(encoding="utf-8")) == {"ok": True}
    assert json.loads((evidence_dir / "metadata.json").read_text(encoding="utf-8")) == {
        "entrypoint": "op",
        "layer": "ops/image.py:t2i",
    }
    manifest = json.loads((evidence_dir / "freeze_manifest.json").read_text(encoding="utf-8"))
    assert manifest["missing"] == []
    assert not (evidence_dir / "evidence").exists()
    assert (unrelated / "keep.txt").read_text(encoding="utf-8") == "keep"


def test_capture_hoists_structural_artifacts_to_pack_root_and_surfaces_actions(tmp_path: Path) -> None:
    adapter = VibeComfyProjectAdapter(name="vibecomfy", repo_root=tmp_path)
    scenario = _scenario("add-save-node-finalize")
    scenario.extras["required_frozen_evidence"] = [
        "evidence/compiled_api.json",
        "evidence/metadata.json",
        "evidence/actions.jsonl",
    ]
    run = _run()
    run.mode = sisypy.RunMode.STRUCTURAL
    run.dispatcher = "deepseek-subagent"
    evidence_dir = tmp_path / "reports" / "case-1"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "report.md").write_text("actor report stays intact\n", encoding="utf-8")
    (evidence_dir / "actions.jsonl").write_text(
        json.dumps({"action": {"action_type": "command", "command": "subagent-launcher"}}) + "\n",
        encoding="utf-8",
    )
    (evidence_dir / "manifest.json").write_text(
        json.dumps({"files": {"report.md": "report.md", "actions.jsonl": "actions.jsonl"}}),
        encoding="utf-8",
    )

    adapter.capture(scenario, run, evidence_dir)

    compiled_api = json.loads((evidence_dir / "compiled_api.json").read_text(encoding="utf-8"))
    class_types = {node.get("class_type") for node in compiled_api.values() if isinstance(node, dict)}
    assert "SaveImage" in class_types
    assert (evidence_dir / "metadata.json").is_file()
    assert (evidence_dir / "report.md").read_text(encoding="utf-8") == "actor report stays intact\n"
    assert not (evidence_dir / "evidence").exists()

    actions_text = (evidence_dir / "actions.jsonl").read_text(encoding="utf-8")
    assert '"op": "block.apply"' in actions_text
    assert '"op": "finalize_metadata"' in actions_text
    assert "subagent-launcher" in actions_text

    tree_after = (evidence_dir / "tree_after.txt").read_text(encoding="utf-8")
    assert "F compiled_api.json" in tree_after
    assert "F metadata.json" in tree_after
    assert "F actions.jsonl" in tree_after

    capture_notes = (evidence_dir / "capture.notes").read_text(encoding="utf-8")
    assert "Project Evidence File: compiled_api.json" in capture_notes
    assert "SaveImage" in capture_notes
    assert "Project Evidence File: metadata.json" in capture_notes
    assert '"requirements"' in capture_notes
    assert "sd_xl_base_1.0.safetensors" in capture_notes

    from sisypy.assessor import _assemble_evidence_sections

    assessor_input = _assemble_evidence_sections(sisypy.EvidencePack(evidence_dir=str(evidence_dir)))
    assert "Project Evidence File: compiled_api.json" in assessor_input
    assert "SaveImage" in assessor_input
    assert "Project Evidence File: metadata.json" in assessor_input
    assert "sd_xl_base_1.0.safetensors" in assessor_input

    manifest = json.loads((evidence_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["files"]["compiled_api.json"] == "compiled_api.json"
    assert manifest["files"]["metadata.json"] == "metadata.json"

    checks = adapter.project_universal_checks(scenario, evidence_dir)
    assert checks["required_frozen_evidence"]["passed"] is True


def test_capture_surfaces_produced_outputs_and_recipe_content_to_assessor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = VibeComfyProjectAdapter(name="vibecomfy", repo_root=tmp_path)
    scenario = _scenario("produced-artifacts")
    scenario.extras["required_frozen_evidence"] = [
        "evidence/compiled_api.json",
        "evidence/metadata.json",
    ]
    run = _run()
    run.mode = sisypy.RunMode.STRUCTURAL
    run.dispatcher = "deepseek-subagent"
    evidence_dir = tmp_path / "reports" / "case-produced"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "manifest.json").write_text(json.dumps({"files": {}}), encoding="utf-8")

    image_bytes = b"structural image placeholder\n"
    recipe_text = (
        "# forked z_image recipe\n"
        "READY_METADATA = {'ready_template': 'image/z_image'}\n"
        "def build():\n"
        "    return 'z_image content'\n"
    )

    def fake_structural_evidence(scenario, run, frozen_root):
        del scenario, run
        (frozen_root / "compiled_api.json").write_text(
            json.dumps({"1": {"class_type": "SaveImage"}}),
            encoding="utf-8",
        )
        (frozen_root / "metadata.json").write_text(
            json.dumps({"entrypoint": "op", "layer": "ops/image.py:t2i"}),
            encoding="utf-8",
        )
        (frozen_root / "outputs").mkdir(parents=True, exist_ok=True)
        (frozen_root / "outputs" / "image.png").write_bytes(image_bytes)
        recipe_path = frozen_root / "workspace" / "recipes" / "m2_z_image_fork.py"
        recipe_path.parent.mkdir(parents=True, exist_ok=True)
        recipe_path.write_text(recipe_text, encoding="utf-8")
        return {"scenario": "produced-artifacts"}

    monkeypatch.setattr(adapter, "_capture_structural_evidence", fake_structural_evidence)

    adapter.capture(scenario, run, evidence_dir)

    capture_notes = (evidence_dir / "capture.notes").read_text(encoding="utf-8")
    assert "Project Evidence File: outputs/image.png" in capture_notes
    assert f"outputs/image.png - {len(image_bytes)} bytes" in capture_notes
    assert "Project Evidence File: workspace/recipes/m2_z_image_fork.py" in capture_notes
    assert "ready_template': 'image/z_image" in capture_notes
    assert "z_image content" in capture_notes

    tree_after = (evidence_dir / "tree_after.txt").read_text(encoding="utf-8")
    assert f"F outputs/image.png - {len(image_bytes)} bytes" in tree_after
    assert "F workspace/recipes/m2_z_image_fork.py -" in tree_after

    from sisypy.assessor import _assemble_evidence_sections

    assessor_input = _assemble_evidence_sections(sisypy.EvidencePack(evidence_dir=str(evidence_dir)))
    assert f"outputs/image.png - {len(image_bytes)} bytes" in assessor_input
    assert "workspace/recipes/m2_z_image_fork.py" in assessor_input
    assert "z_image content" in assessor_input


def test_classify_success_fails_missing_required_frozen_evidence_even_with_report(tmp_path: Path) -> None:
    adapter = VibeComfyProjectAdapter(name="vibecomfy", repo_root=tmp_path)
    scenario = _scenario()
    scenario.extras["required_frozen_evidence"] = ["evidence/compiled_prompt.json"]
    evidence_dir = tmp_path / "evidence-pack"
    evidence_dir.mkdir()
    (evidence_dir / "report.md").write_text("# success\n", encoding="utf-8")
    pack = sisypy.EvidencePack(
        evidence_dir=str(evidence_dir),
        files={"report.md": str(evidence_dir / "report.md")},
    )

    proof_level = adapter.classify_success(scenario, pack)

    assert proof_level is sisypy.SuccessProofLevel.AUTHORED


def test_project_universal_checks_report_missing_required_frozen_evidence(tmp_path: Path) -> None:
    adapter = VibeComfyProjectAdapter(name="vibecomfy", repo_root=tmp_path)
    scenario = _scenario()
    scenario.extras["required_frozen_evidence"] = ["evidence/compiled_prompt.json", "evidence/metadata.json"]
    evidence_dir = tmp_path / "evidence-pack"
    (evidence_dir / "evidence").mkdir(parents=True)
    (evidence_dir / "evidence" / "metadata.json").write_text("{}", encoding="utf-8")

    checks = adapter.project_universal_checks(scenario, evidence_dir)

    assert checks["required_frozen_evidence"]["passed"] is False
    assert checks["required_frozen_evidence"]["missing"] == ["evidence/compiled_prompt.json"]


def test_classify_success_fails_on_faking_actor_evidence(tmp_path: Path) -> None:
    """classify_success must FAIL on faking-actor evidence even with report.md."""
    from agentic.actors import build_faking_structural_chain

    adapter = VibeComfyProjectAdapter(name="vibecomfy", repo_root=tmp_path)
    report_dir = tmp_path / "reports" / "faking"

    build_faking_structural_chain(report_dir)

    scenario = _scenario()
    scenario.extras["required_frozen_evidence"] = [
        "evidence/stage1/compiled_api.json",
        "evidence/stage2/compiled_api.json",
    ]
    evidence_dir = tmp_path / "evidence-pack"
    evidence_dir.mkdir()
    (evidence_dir / "report.md").write_text((report_dir / "report.md").read_text(encoding="utf-8"))
    pack = sisypy.EvidencePack(
        evidence_dir=str(evidence_dir),
        files={"report.md": str(evidence_dir / "report.md")},
    )

    proof_level = adapter.classify_success(scenario, pack)

    assert proof_level is sisypy.SuccessProofLevel.AUTHORED


# ── Adversarial evidence-vs-narrative tests ──────────────────────────────────

def _build_genuine_evidence_pack(
    tmp_path: Path,
    adapter: VibeComfyProjectAdapter,
    scenario_name: str = "positive-chain",
) -> tuple[sisypy.Scenario, Path, sisypy.EvidencePack]:
    """Build a genuine evidence pack with all required evidence files present.

    Uses the positive structural chain actor to produce compiled API JSON,
    metadata JSON, actions.jsonl, and output placeholders.  Returns the
    scenario with required_frozen_evidence set and the EvidencePack.
    """
    from agentic.actors import build_positive_structural_chain

    report_dir = tmp_path / "reports" / "genuine"
    build_positive_structural_chain(report_dir)

    scenario = sisypy.Scenario(name=scenario_name)
    scenario.extras["required_frozen_evidence"] = [
        "evidence/stage1/compiled_api.json",
        "evidence/stage1/metadata.json",
        "evidence/stage2/compiled_api.json",
        "evidence/stage2/metadata.json",
        "evidence/actions.jsonl",
    ]

    evidence_dir = tmp_path / "evidence-pack-genuine"
    evidence_dir.mkdir(parents=True)
    frozen = evidence_dir / "evidence"
    frozen.mkdir()

    # Copy all evidence files from the actor output into the frozen directory
    import shutil

    for rel_path in [
        "stage1/compiled_api.json",
        "stage1/metadata.json",
        "stage2/compiled_api.json",
        "stage2/metadata.json",
        "actions.jsonl",
    ]:
        src = report_dir / rel_path
        dst = frozen / rel_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dst))

    # Also copy report.md, stdout, stderr for file listing
    for name in ["report.md", "stdout.txt", "stderr.txt"]:
        src = report_dir / name
        if src.is_file():
            dst = evidence_dir / name
            shutil.copy2(str(src), str(dst))

    # Build files dict
    files: dict[str, str] = {}
    for p in evidence_dir.rglob("*"):
        if p.is_file():
            files[str(p.relative_to(evidence_dir))] = str(p)

    pack = sisypy.EvidencePack(evidence_dir=str(evidence_dir), files=files)
    return scenario, evidence_dir, pack


def test_report_md_removal_does_not_block_genuine_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Removing report.md must not prevent genuine evidence from passing.

    The harness must classify success from frozen evidence (compiled API,
    metadata, actions.jsonl), NOT from actor narrative in report.md.
    """
    monkeypatch.chdir(tmp_path)
    adapter = VibeComfyProjectAdapter(name="vibecomfy", repo_root=tmp_path)
    scenario, evidence_dir, pack = _build_genuine_evidence_pack(tmp_path, adapter)

    # Remove report.md to prove it is not required for pass/fail
    report_path = evidence_dir / "report.md"
    if report_path.is_file():
        report_path.unlink()
    # Also remove from files dict
    pack.files.pop("report.md", None)

    proof_level = adapter.classify_success(scenario, pack)

    # Must be at least COMPILED (all evidence present, checks pass or
    # report.md absence is irrelevant).  Ideally VALIDATED if universal
    # checks also pass without report.md.
    assert proof_level in (
        sisypy.SuccessProofLevel.COMPILED,
        sisypy.SuccessProofLevel.VALIDATED,
    ), (
        f"Expected COMPILED or VALIDATED without report.md, got {proof_level.value!r}. "
        "The harness must not require report.md for evidence-based classification."
    )


def test_report_md_lies_but_evidence_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When report.md claims failure but evidence is complete and consistent,
    the harness must NOT be fooled by the lying narrative."""
    monkeypatch.chdir(tmp_path)
    adapter = VibeComfyProjectAdapter(name="vibecomfy", repo_root=tmp_path)
    scenario, evidence_dir, pack = _build_genuine_evidence_pack(tmp_path, adapter)

    # Overwrite report.md with a deceptive failure narrative
    (evidence_dir / "report.md").write_text(
        "# FAILED\n\nThe pipeline crashed. Nothing worked.\nAll outputs are corrupt.\n",
        encoding="utf-8",
    )

    proof_level = adapter.classify_success(scenario, pack)

    # Evidence is complete → must NOT be AUTHORED (which indicates missing evidence)
    assert proof_level is not sisypy.SuccessProofLevel.AUTHORED, (
        "Deceptive report.md must not cause AUTHORED classification when evidence is present."
    )
    assert proof_level in (
        sisypy.SuccessProofLevel.COMPILED,
        sisypy.SuccessProofLevel.VALIDATED,
    ), (
        f"Expected COMPILED or VALIDATED with lying report.md, got {proof_level.value!r}."
    )


def test_missing_compiled_api_fails_despite_plausible_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Removing compiled API evidence must cause failure even with a
    detailed, plausible report.md present."""
    monkeypatch.chdir(tmp_path)
    adapter = VibeComfyProjectAdapter(name="vibecomfy", repo_root=tmp_path)
    scenario, evidence_dir, pack = _build_genuine_evidence_pack(tmp_path, adapter)

    # Keep a detailed report.md
    (evidence_dir / "report.md").write_text(
        "# SUCCESS\n\n"
        "Stage 1 compiled successfully.\n"
        "Stage 2 compiled successfully.\n"
        "All API nodes validated. Chain metadata linked correctly.\n",
        encoding="utf-8",
    )

    # Remove a critical evidence file: stage1/compiled_api.json
    frozen = evidence_dir / "evidence"
    (frozen / "stage1" / "compiled_api.json").unlink()
    pack.files = {
        k: v
        for k, v in pack.files.items()
        if "stage1/compiled_api.json" not in k
    }

    proof_level = adapter.classify_success(scenario, pack)

    # Must be AUTHORED (missing required evidence) regardless of report.md
    assert proof_level is sisypy.SuccessProofLevel.AUTHORED, (
        f"Expected AUTHORED when compiled_api.json is missing, got {proof_level.value!r}."
    )


def test_universal_checks_missing_required_evidence_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """project_universal_checks must report failure when required frozen
    evidence files are missing, even if report.md is present and plausible."""
    monkeypatch.chdir(tmp_path)
    adapter = VibeComfyProjectAdapter(name="vibecomfy", repo_root=tmp_path)
    scenario, evidence_dir, pack = _build_genuine_evidence_pack(tmp_path, adapter)

    # Remove stage2/metadata.json from evidence
    (evidence_dir / "evidence" / "stage2" / "metadata.json").unlink()

    checks = adapter.project_universal_checks(scenario, evidence_dir)

    assert checks["required_frozen_evidence"]["passed"] is False
    assert "evidence/stage2/metadata.json" in checks["required_frozen_evidence"]["missing"]
    assert checks["required_frozen_evidence"]["severity"] == "error"


def test_capture_structural_evidence_routes_m2_slug_and_writes_workspace_git_diff(tmp_path: Path) -> None:
    from sisypy import RunMode

    adapter = VibeComfyProjectAdapter(name="vibecomfy", repo_root=tmp_path)
    scenario = _scenario("fork-z-image-copy-to-recipe")
    run = _run()
    run.mode = RunMode.STRUCTURAL
    run.dispatcher = "fake"

    manifest = adapter._capture_structural_evidence(
        scenario,
        run,
        tmp_path / "reports" / "fork-z-image-copy-to-recipe" / "evidence",
    )

    assert manifest is not None
    assert manifest["scenario"] == "fork-z-image-copy-to-recipe"
    git_diff_path = Path(manifest["git_diff_path"])
    assert git_diff_path.is_file()
    git_diff = git_diff_path.read_text(encoding="utf-8")
    assert "recipes/m2_z_image_fork.py" in git_diff
    assert "ready_templates/" not in git_diff


def test_capture_structural_evidence_returns_none_for_unknown_non_faking_structural_scenario(
    tmp_path: Path,
) -> None:
    from sisypy import RunMode

    adapter = VibeComfyProjectAdapter(name="vibecomfy", repo_root=tmp_path)
    scenario = _scenario("unknown-m2-slug")
    run = _run()
    run.mode = RunMode.STRUCTURAL
    run.dispatcher = "fake"

    manifest = adapter._capture_structural_evidence(
        scenario,
        run,
        tmp_path / "reports" / "unknown-m2-slug" / "evidence",
    )

    assert manifest is None


# ── M2 adapter dispatch and faking-guard tests ───────────────────────────────


def test_all_seven_m2_slugs_route_through_m2_builders_dict(
    tmp_path: Path,
) -> None:
    """Every M2 scenario slug must be present in _M2_BUILDERS and produce a
    non-None manifest when dispatched structurally with dispatcher='fake'."""
    from sisypy import RunMode

    from agentic.adapter import _M2_BUILDERS

    all_m2_slugs = [
        "generate-image-canonical-op",
        "run-wan-t2v-ready-cli",
        "audio-t2a-unwired-limit",
        "audio-song-escape-hatch-positive",
        "image-edit-unwired-limit",
        "fork-z-image-copy-to-recipe",
        "impossible-8k-free-tier-video",
    ]

    adapter = VibeComfyProjectAdapter(name="vibecomfy", repo_root=tmp_path)

    for slug in all_m2_slugs:
        # 1) The slug must be a key in _M2_BUILDERS
        assert slug in _M2_BUILDERS, (
            f"Slug {slug!r} is not in _M2_BUILDERS dispatch dict"
        )
        builder = _M2_BUILDERS[slug]
        assert callable(builder), f"_M2_BUILDERS[{slug!r}] is not callable"

        # 2) Dispatching through _capture_structural_evidence must return a
        #    non-None manifest
        scenario = _scenario(slug)
        run = _run()
        run.mode = RunMode.STRUCTURAL
        run.dispatcher = "fake"

        report_dir = tmp_path / "reports" / slug
        manifest = adapter._capture_structural_evidence(
            scenario,
            run,
            report_dir,
        )

        assert manifest is not None, (
            f"_capture_structural_evidence returned None for slug {slug!r}"
        )
        assert isinstance(manifest, dict), (
            f"Manifest for {slug!r} is not a dict: {type(manifest)}"
        )


def test_unknown_structural_scenario_does_not_crash_and_returns_none(
    tmp_path: Path,
) -> None:
    """Multiple unknown slugs must all return None without raising exceptions."""
    from sisypy import RunMode

    adapter = VibeComfyProjectAdapter(name="vibecomfy", repo_root=tmp_path)

    unknown_slugs = [
        "completely-bogus-slug",
        "not-a-real-scenario",
        "gobbledygook-12345",
    ]

    for slug in unknown_slugs:
        scenario = _scenario(slug)
        run = _run()
        run.mode = RunMode.STRUCTURAL
        run.dispatcher = "fake"

        report_dir = tmp_path / "reports" / slug
        report_dir.mkdir(parents=True, exist_ok=True)

        # Must not raise
        manifest = adapter._capture_structural_evidence(
            scenario,
            run,
            report_dir,
        )

        assert manifest is None, (
            f"Unknown slug {slug!r} should return None, got {manifest!r}"
        )


def test_m2_required_frozen_evidence_disjoint_from_faking_outputs(
    tmp_path: Path,
) -> None:
    """For every M2 scenario, required_frozen_evidence must have an empty
    intersection with the files produced by the generic faking actor.

    The faking actor produces: report.md, stdout.txt, stderr.txt.
    If any M2 scenario's required evidence set includes one of these, the
    faking actor could pass a purely narrative-based check, defeating the
    evidence-guard design.
    """
    from agentic.actors import build_faking_structural_chain

    # Files the faking actor actually writes to disk
    faking_dir = tmp_path / "reports" / "faking-guard-check"
    build_faking_structural_chain(faking_dir)
    faking_files = {
        str(p.relative_to(faking_dir))
        for p in faking_dir.rglob("*")
        if p.is_file()
    }
    # Normalize for evidence/ prefix matching: faking actor writes e.g.
    # "report.md", "stdout.txt", "stderr.txt"
    faking_evidence = {f"evidence/{f}" for f in faking_files}

    all_m2_slugs = [
        "generate-image-canonical-op",
        "run-wan-t2v-ready-cli",
        "audio-t2a-unwired-limit",
        "audio-song-escape-hatch-positive",
        "image-edit-unwired-limit",
        "fork-z-image-copy-to-recipe",
        "impossible-8k-free-tier-video",
    ]

    # Helper to load YAML (reuses the structural test helper approach)
    import sys as _sys

    sisypy_path = Path.home() / "Documents" / "reigh-workspace" / "sisypy"
    if str(sisypy_path) not in _sys.path:
        _sys.path.insert(0, str(sisypy_path))
    from sisypy.runner import load_scenario

    for slug in all_m2_slugs:
        yaml_name = slug.replace("-", "_") + ".yaml"
        scenario_path = (
            Path(__file__).resolve().parent.parent
            / "agentic"
            / "scenarios"
            / yaml_name
        )
        scenario = load_scenario(scenario_path)

        required = set(scenario.extras.get("required_frozen_evidence", []))
        assert len(required) >= 1, f"[{slug}] has no required_frozen_evidence"

        intersection = required & faking_evidence
        assert not intersection, (
            f"[{slug}] required_frozen_evidence shares files with faking actor: {intersection}. "
            f"Faking files: {sorted(faking_evidence)}. "
            f"Required: {sorted(required)}."
        )

    # Also sanity-check: faking actor must produce at least report.md
    assert "evidence/report.md" in faking_evidence, (
        "Faking actor did not produce report.md — test assumption broken"
    )


# ── M2 classification tests (genuine-vs-faking for positive scenarios) ────────

M2_POSITIVE_CLASSIFICATION_SLUGS = [
    "generate-image-canonical-op",
    "run-wan-t2v-ready-cli",
    "audio-song-escape-hatch-positive",
    "fork-z-image-copy-to-recipe",
]


def _build_m2_genuine_evidence_pack(
    slug: str,
    tmp_path: Path,
    adapter: VibeComfyProjectAdapter,
) -> tuple[sisypy.Scenario, Path, sisypy.EvidencePack]:
    """Build a genuine M2 evidence pack using the structural builder.

    Produces all required frozen evidence files declared in the scenario
    YAML, copies them into a proper evidence pack directory structure, and
    returns the scenario (with required_frozen_evidence set), evidence_dir,
    and EvidencePack.
    """
    import shutil

    from agentic.adapter import _M2_BUILDERS

    builder = _M2_BUILDERS[slug]

    report_dir = tmp_path / "reports" / slug
    builder(report_dir)

    # Load scenario YAML to get required_frozen_evidence
    import sys as _sys

    sisypy_path = Path.home() / "Documents" / "reigh-workspace" / "sisypy"
    if str(sisypy_path) not in _sys.path:
        _sys.path.insert(0, str(sisypy_path))
    from sisypy.runner import load_scenario

    yaml_name = slug.replace("-", "_") + ".yaml"
    scenario_path = (
        Path(__file__).resolve().parent.parent
        / "agentic"
        / "scenarios"
        / yaml_name
    )
    scenario = load_scenario(scenario_path)

    evidence_dir = tmp_path / f"evidence-pack-{slug}"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    frozen = evidence_dir / "evidence"
    frozen.mkdir(exist_ok=True)

    # Copy all builder-produced files into the frozen directory
    for p in report_dir.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(report_dir)
        dst = frozen / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(p), str(dst))

    # Build files dict
    files: dict[str, str] = {}
    for p in evidence_dir.rglob("*"):
        if p.is_file():
            files[str(p.relative_to(evidence_dir))] = str(p)

    pack = sisypy.EvidencePack(evidence_dir=str(evidence_dir), files=files)
    return scenario, evidence_dir, pack


@pytest.mark.parametrize("slug", M2_POSITIVE_CLASSIFICATION_SLUGS)
def test_m2_genuine_evidence_passes_classification(
    slug: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Genuine M2 evidence from structural builders must pass classification.

    For every positive M2 scenario, the genuine evidence pack produced by
    the structural builder must achieve at least COMPILED proof level —
    never AUTHORED.  This proves that real frozen evidence satisfies the
    required_frozen_evidence contract.
    """
    monkeypatch.chdir(tmp_path)
    adapter = VibeComfyProjectAdapter(name="vibecomfy", repo_root=tmp_path)
    scenario, _evidence_dir, pack = _build_m2_genuine_evidence_pack(
        slug, tmp_path, adapter
    )

    proof_level = adapter.classify_success(scenario, pack)

    assert proof_level is not sisypy.SuccessProofLevel.AUTHORED, (
        f"[{slug}] genuine evidence must not be AUTHORED. "
        f"Got {proof_level.value!r}. Check that all required_frozen_evidence "
        f"files are present in the evidence pack."
    )
    assert proof_level in (
        sisypy.SuccessProofLevel.COMPILED,
        sisypy.SuccessProofLevel.VALIDATED,
    ), (
        f"[{slug}] genuine evidence must be COMPILED or VALIDATED. "
        f"Got {proof_level.value!r}."
    )


@pytest.mark.parametrize("slug", M2_POSITIVE_CLASSIFICATION_SLUGS)
def test_m2_faking_evidence_fails_classification(
    slug: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Faking evidence must fail classification for every positive M2 scenario.

    The generic faking actor produces only narrative files (report.md,
    stdout.txt, stderr.txt) and never produces required frozen evidence
    like compiled_api.json, metadata.json, actions.jsonl, etc.

    For each positive M2 scenario, construct a deceptively positive
    report.md alongside the faking output and prove that classify_success
    returns AUTHORED — the faking actor cannot pass as real frozen proof.
    """
    monkeypatch.chdir(tmp_path)
    from agentic.actors import build_faking_structural_chain

    # Load scenario YAML to get required_frozen_evidence
    import sys as _sys

    sisypy_path = Path.home() / "Documents" / "reigh-workspace" / "sisypy"
    if str(sisypy_path) not in _sys.path:
        _sys.path.insert(0, str(sisypy_path))
    from sisypy.runner import load_scenario

    yaml_name = slug.replace("-", "_") + ".yaml"
    scenario_path = (
        Path(__file__).resolve().parent.parent
        / "agentic"
        / "scenarios"
        / yaml_name
    )
    scenario = load_scenario(scenario_path)

    # Build faking evidence
    faking_dir = tmp_path / "reports" / "faking"
    build_faking_structural_chain(faking_dir)

    # Overwrite report.md with a deceptively positive narrative
    (faking_dir / "report.md").write_text(
        "# SUCCESS\n\n"
        "All pipeline stages completed successfully.\n"
        "Compiled API JSON validated. Metadata linked correctly.\n"
        "Evidence pack is complete and consistent.\n",
        encoding="utf-8",
    )

    evidence_dir = tmp_path / f"evidence-pack-faking-{slug}"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    # Copy only the faking actor's files
    import shutil

    for p in faking_dir.rglob("*"):
        if not p.is_file():
            continue
        dst = evidence_dir / p.relative_to(faking_dir)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(p), str(dst))

    files: dict[str, str] = {}
    for p in evidence_dir.rglob("*"):
        if p.is_file():
            files[str(p.relative_to(evidence_dir))] = str(p)

    pack = sisypy.EvidencePack(evidence_dir=str(evidence_dir), files=files)

    adapter = VibeComfyProjectAdapter(name="vibecomfy", repo_root=tmp_path)
    proof_level = adapter.classify_success(scenario, pack)

    assert proof_level is sisypy.SuccessProofLevel.AUTHORED, (
        f"[{slug}] faking evidence must be AUTHORED. "
        f"Got {proof_level.value!r}. "
        f"The faking actor must not satisfy required_frozen_evidence."
    )
