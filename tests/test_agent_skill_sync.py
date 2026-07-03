from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts import sync_agent_skill


ROOT = Path(__file__).resolve().parents[1]
AUXILIARY_SKILLS = {
    "add-comfy-workflow-template",
    "debug-comfy-workflow",
    "explain-comfy-workflow",
    "edit-comfy-workflow",
    "reorganise-comfy-workflow",
    "run-comfy-workflow",
    "search-comfy-workflows",
    "vibecomfy-setup",
}


def test_agent_skill_surfaces_are_synced() -> None:
    source = (ROOT / "docs" / "agent-skill" / "SKILL.md").read_text(encoding="utf-8")
    reference = ROOT / "docs" / "agent-skill" / "REFERENCE.md"

    assert set(sync_agent_skill.EXPECTED_AUXILIARY_SKILLS) == AUXILIARY_SKILLS
    assert "sync-vibecomfy-skills" in sync_agent_skill.OBSOLETE_AUXILIARY_SKILLS
    assert "name: vibecomfy" in source
    assert "REFERENCE.md" in source
    assert reference.exists(), f"{reference} is missing"
    for skill in AUXILIARY_SKILLS:
        skill_source = ROOT / "docs" / "agent-skill" / "skills" / skill / "SKILL.md"
        assert skill_source.exists(), f"{skill_source} is missing"
        assert f"name: {skill}" in skill_source.read_text(encoding="utf-8")
    assert not (ROOT / "CLAUDE.md").exists()
    assert not (ROOT / "AGENTS.md").exists()


def test_agent_skill_sync_check_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/sync_agent_skill.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_install_user_updates_codex_agents_md(tmp_path: Path) -> None:
    for harness in (".claude", ".codex", ".hermes"):
        (tmp_path / harness / "skills").mkdir(parents=True)
    stale_target = tmp_path / ".claude" / "skills" / "vibecomfy"
    stale_target.symlink_to(tmp_path / "stale-vibecomfy")
    obsolete_target = tmp_path / ".codex" / "skills" / "sync-vibecomfy-skills"
    obsolete_target.symlink_to(ROOT / "docs" / "agent-skill" / "skills" / "sync-vibecomfy-skills")
    agents_md = tmp_path / ".codex" / "AGENTS.md"
    agents_md.write_text("# Existing Codex instructions\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "scripts/sync_agent_skill.py", "--install-user"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env={
            "HOME": str(tmp_path),
            "HERMES_HOME": str(tmp_path / ".hermes"),
        },
    )

    assert result.returncode == 0, result.stderr
    for harness in (".claude", ".codex", ".hermes"):
        assert (tmp_path / harness / "skills" / "vibecomfy").is_symlink()
        for skill in AUXILIARY_SKILLS:
            assert (tmp_path / harness / "skills" / skill).is_symlink()
        assert not (tmp_path / harness / "skills" / "sync-vibecomfy-skills").exists()
        assert not (tmp_path / harness / "skills" / "sync-vibecomfy-skills").is_symlink()
    updated_agents = agents_md.read_text(encoding="utf-8")
    assert "# Existing Codex instructions" in updated_agents
    assert "<!-- vibecomfy:skillsinker:begin -->" in updated_agents
    assert "`vibecomfy`" in updated_agents
    for skill in AUXILIARY_SKILLS:
        assert f"`{skill}`" in updated_agents
    assert "`sync-vibecomfy-skills`" not in updated_agents
