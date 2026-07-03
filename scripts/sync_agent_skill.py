#!/usr/bin/env python3
"""Check and optionally install the canonical VibeComfy agent skills."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "agent-skill" / "SKILL.md"
SKILLS_SOURCE_DIR = ROOT / "docs" / "agent-skill" / "skills"
EXPECTED_AUXILIARY_SKILLS = (
    "add-comfy-workflow-template",
    "debug-comfy-workflow",
    "explain-comfy-workflow",
    "edit-comfy-workflow",
    "reorganise-comfy-workflow",
    "run-comfy-workflow",
    "search-comfy-workflows",
    "vibecomfy-setup",
)
OBSOLETE_AUXILIARY_SKILLS = (
    "sync-vibecomfy-skills",
)
COPY_TARGETS = ()
LOCAL_COPY_TARGETS = ()
SYMLINK_TARGETS = {}
USER_SKILL_SOURCE = SOURCE.parent
USER_SKILL_TARGET_DIRS = (
    Path.home() / ".claude" / "skills",
    Path.home() / ".codex" / "skills",
    Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))) / "skills",
)
CODEX_AGENTS = Path.home() / ".codex" / "AGENTS.md"
SKILLSINKER_BEGIN = "<!-- vibecomfy:skillsinker:begin -->"
SKILLSINKER_END = "<!-- vibecomfy:skillsinker:end -->"


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def _read_source() -> str:
    if not SOURCE.exists():
        raise SystemExit("docs/agent-skill/SKILL.md is missing")
    content = SOURCE.read_text(encoding="utf-8")
    if not content.startswith("---\n") or "name: vibecomfy" not in content:
        raise SystemExit("docs/agent-skill/SKILL.md must be the canonical VibeComfy skill with frontmatter")
    return content


def _auxiliary_skill_sources() -> dict[str, Path]:
    if not SKILLS_SOURCE_DIR.exists():
        raise SystemExit("docs/agent-skill/skills is missing")
    found = {
        path.parent.name: path.parent
        for path in sorted(SKILLS_SOURCE_DIR.glob("*/SKILL.md"))
    }
    expected = set(EXPECTED_AUXILIARY_SKILLS)
    actual = set(found)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        parts = []
        if missing:
            parts.append(f"missing auxiliary skills: {', '.join(missing)}")
        if extra:
            parts.append(f"unexpected auxiliary skills: {', '.join(extra)}")
        raise SystemExit("; ".join(parts))
    for name, source in found.items():
        content = (source / "SKILL.md").read_text(encoding="utf-8")
        if not content.startswith("---\n") or f"name: {name}" not in content:
            raise SystemExit(f"{_relative(source / 'SKILL.md')} must have matching skill frontmatter")
    return found


def _check_copy(path: Path, expected: str) -> str | None:
    if not path.exists():
        return f"{_relative(path)} is missing"
    actual = path.read_text(encoding="utf-8")
    if actual != expected:
        return f"{_relative(path)} is stale"
    return None


def _check_symlink(path: Path, expected_target: str) -> str | None:
    if not path.is_symlink():
        return f"{_relative(path)} should be a symlink to {expected_target}"
    actual = path.readlink()
    if str(actual) != expected_target:
        return f"{_relative(path)} points to {actual}, expected {expected_target}"
    return None


def check() -> int:
    source = _read_source()
    _auxiliary_skill_sources()
    errors = []
    errors.extend(error for target in COPY_TARGETS if (error := _check_copy(target, source)))
    errors.extend(error for target, link in SYMLINK_TARGETS.items() if (error := _check_symlink(target, link)))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print("Run: python3 scripts/sync_agent_skill.py --apply", file=sys.stderr)
        return 1
    print("Agent skill files are in sync.")
    return 0


def apply() -> int:
    source = _read_source()
    for target in (*COPY_TARGETS, *LOCAL_COPY_TARGETS):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")
        print(f"synced {_relative(target)}")
    for target, link in SYMLINK_TARGETS.items():
        if target.exists() or target.is_symlink():
            if target.is_symlink() and str(target.readlink()) == link:
                print(f"kept {_relative(target)} -> {link}")
                continue
            raise SystemExit(f"{_relative(target)} exists but is not the expected symlink")
        target.symlink_to(link)
        print(f"created {_relative(target)} -> {link}")
    return check()


class SkillSinker:
    """Install the VibeComfy skill into local agent harness surfaces."""

    def __init__(self, source: Path, codex_agents: Path, auxiliary_sources: dict[str, Path]) -> None:
        self.source = source
        self.codex_agents = codex_agents
        self.auxiliary_sources = auxiliary_sources

    def install(self) -> None:
        self._link_skill_dirs()
        self._rewrite_codex_agents()

    def _link_skill_dirs(self) -> None:
        if not self.source.exists():
            raise SystemExit(f"{_relative(self.source)} is missing")
        for target_dir in USER_SKILL_TARGET_DIRS:
            if not target_dir.exists():
                print(f"skipped {target_dir} (parent missing)")
                continue
            self._link_one(target_dir / "vibecomfy", self.source)
            for name, source in self.auxiliary_sources.items():
                self._link_one(target_dir / name, source)
            for name in OBSOLETE_AUXILIARY_SKILLS:
                self._remove_obsolete(target_dir / name)

    @staticmethod
    def _link_one(target: Path, source: Path) -> None:
        if target.is_symlink() and target.resolve() == source.resolve():
            print(f"kept {target} -> {source}")
            return
        if target.is_symlink():
            old_target = target.readlink()
            target.unlink()
            target.symlink_to(source, target_is_directory=True)
            print(f"retargeted {target} from {old_target} to {source}")
            return
        if target.exists() or target.is_symlink():
            raise SystemExit(f"{target} exists; remove it or install manually")
        target.symlink_to(source, target_is_directory=True)
        print(f"linked {target} -> {source}")

    @staticmethod
    def _remove_obsolete(target: Path) -> None:
        if not target.is_symlink():
            return
        old_target = target.readlink()
        target.unlink()
        print(f"removed obsolete {target} -> {old_target}")

    def _rewrite_codex_agents(self) -> None:
        if not self.codex_agents.parent.exists():
            print(f"skipped {self.codex_agents} (parent missing)")
            return
        block = self._render_codex_block()
        existing = self.codex_agents.read_text(encoding="utf-8") if self.codex_agents.exists() else ""
        updated = self._merge_block(existing, block)
        if updated == existing:
            print(f"kept {self.codex_agents} SkillSinker block")
            return
        self.codex_agents.write_text(updated, encoding="utf-8")
        print(f"updated {self.codex_agents} SkillSinker block")

    def _render_codex_block(self) -> str:
        auxiliary_lines = "\n".join(
            f"- `{name}` ({source}): VibeComfy package skill."
            for name, source in sorted(self.auxiliary_sources.items())
        )
        return (
            f"{SKILLSINKER_BEGIN}\n"
            "# VibeComfy skills\n\n"
            f"- `vibecomfy` ({self.source}): Use VibeComfy to load, edit, validate, port, and run ComfyUI workflows through Python ready templates.\n"
            f"{auxiliary_lines}\n"
            f"{SKILLSINKER_END}"
        )

    @staticmethod
    def _merge_block(existing: str, block: str) -> str:
        if SKILLSINKER_BEGIN in existing and SKILLSINKER_END in existing:
            before, _, rest = existing.partition(SKILLSINKER_BEGIN)
            _, _, after = rest.partition(SKILLSINKER_END)
            return f"{before}{block}{after}"
        if not existing:
            return block + "\n"
        suffix = "" if existing.endswith("\n") else "\n"
        return f"{existing}{suffix}\n{block}\n"


def install_user() -> int:
    apply_result = apply()
    if apply_result != 0:
        return apply_result
    SkillSinker(USER_SKILL_SOURCE, CODEX_AGENTS, _auxiliary_skill_sources()).install()
    return check()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="update mirrored skill files")
    parser.add_argument(
        "--install-user",
        action="store_true",
        help="use SkillSinker to symlink the local skill into detected harnesses and update Codex AGENTS.md",
    )
    args = parser.parse_args(argv)
    if args.install_user:
        return install_user()
    return apply() if args.apply else check()


if __name__ == "__main__":
    raise SystemExit(main())
