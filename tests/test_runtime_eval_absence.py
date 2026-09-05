from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = (
    "vibecomfy",
    "tests",
    "scripts",
    "tools",
    "recipes",
    "ready_templates",
)


def _python_files() -> list[Path]:
    files: list[Path] = []
    for root_name in SCAN_ROOTS:
        root = REPO_ROOT / root_name
        if not root.exists():
            continue
        files.extend(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)
    return sorted(files)


REMOVED_RUNTIME_EVAL_MODULES = {
    "vibecomfy.runtime.eval_plan",
    "vibecomfy.runtime.eval_prompt",
    "vibecomfy.runtime.metadata",
    "vibecomfy.runtime.preview_types",
}


def _runtime_eval_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    findings: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in REMOVED_RUNTIME_EVAL_MODULES:
                    findings.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module in REMOVED_RUNTIME_EVAL_MODULES:
                findings.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}: from {module} import ...")
            if module == "vibecomfy.runtime":
                for alias in node.names:
                    if alias.name in {"eval_plan", "eval_prompt", "metadata", "preview_types"}:
                        findings.append(
                            f"{path.relative_to(REPO_ROOT)}:{node.lineno}: from vibecomfy.runtime import {alias.name}"
                        )
    return findings


def test_no_live_code_imports_removed_flat_runtime_eval_modules() -> None:
    findings: list[str] = []
    for path in _python_files():
        findings.extend(_runtime_eval_imports(path))

    assert findings == []


def test_eval_and_owned_commands_have_no_raw_queue_authority() -> None:
    roots = [
        REPO_ROOT / "vibecomfy" / "runtime" / "eval",
        REPO_ROOT / "vibecomfy" / "commands" / "runtime.py",
        REPO_ROOT / "vibecomfy" / "commands" / "run.py",
    ]
    forbidden = {"queue_prompt", "queue_prompt_api", "_post_prompt", "ComfyClient", "comfy_server", "queue_api_for_plan"}
    findings: list[str] = []
    paths = [roots[-2], roots[-1]]
    paths.extend(path for path in roots[0].glob("*.py"))
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in forbidden:
                findings.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}:{node.id}")
            if isinstance(node, ast.Attribute) and node.attr in forbidden:
                findings.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}:{node.attr}")
    assert findings == []
