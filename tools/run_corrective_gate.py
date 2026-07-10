"""Fail-closed, runner-separated corrective trust gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PHASE_EXTENSIONS = {"python": ".py", "node": ".mjs", "playwright": ".mjs"}
DEFAULT_TIMEOUTS = {"python": 600, "node": 600, "playwright": 300}
SENSITIVE_ENV = re.compile(r"(?:TOKEN|KEY|SECRET|PASSWORD|CREDENTIAL|AUTH)", re.I)


class GateError(RuntimeError):
    """An acceptance invariant failed closed."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_identity(repo_root: Path) -> dict[str, Any]:
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, check=True,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        ).stdout.strip()
        dirty = bool(subprocess.run(
            ["git", "status", "--porcelain"], cwd=repo_root, check=True,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        ).stdout.strip())
    except (OSError, subprocess.CalledProcessError) as exc:
        raise GateError(f"cannot establish git identity: {exc}") from exc
    return {"head": head, "dirty": dirty}


def _sanitize(text: str, repo_root: Path) -> str:
    value = str(text)
    replacements = [(str(repo_root), "<repo>"), (str(Path.home()), "<home>")]
    replacements.extend(
        (secret, "<redacted>")
        for name, secret in os.environ.items()
        if secret and len(secret) >= 8 and SENSITIVE_ENV.search(name)
    )
    for source, replacement in sorted(replacements, key=lambda item: len(item[0]), reverse=True):
        value = value.replace(source, replacement)
    return re.sub(
        r"([?&](?:token|key|secret|password|auth)=)[^&\s]+",
        r"\1<redacted>",
        value,
        flags=re.I,
    )


def load_inventory(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError(f"inventory is missing or malformed: {exc}") from exc
    if payload.get("schema_version") != 1:
        raise GateError("inventory schema_version must be 1")
    return payload


def validate_inventory(payload: dict[str, Any], repo_root: Path) -> None:
    seen: set[str] = set()
    for phase, extension in PHASE_EXTENSIONS.items():
        config = payload.get(phase)
        paths = config.get("paths") if isinstance(config, dict) else None
        minimum = config.get("minimum_collected") if isinstance(config, dict) else None
        if not isinstance(paths, list) or not paths or not isinstance(minimum, int) or minimum < 1:
            raise GateError(f"{phase} requires non-empty paths and minimum_collected >= 1")
        for relative in paths:
            if not isinstance(relative, str) or Path(relative).suffix != extension:
                raise GateError(f"{phase} inventory contains wrong-runner path: {relative!r}")
            if relative in seen:
                raise GateError(f"inventory path is duplicated across runners: {relative}")
            seen.add(relative)
            target = (repo_root / relative).resolve()
            if repo_root not in target.parents or not target.is_file():
                raise GateError(f"inventory path is absent or escapes the repository: {relative}")

    expected = payload.get("quarantine_sha256")
    if not isinstance(expected, dict) or not expected:
        raise GateError("quarantine_sha256 must lock the complete quarantine surface")
    actual_paths = {
        path.relative_to(repo_root).as_posix()
        for path in (repo_root / "tests" / "quarantine").glob("*.txt")
    }
    if set(expected) != actual_paths:
        raise GateError("quarantine file set drifted from the locked inventory")
    for relative, digest in expected.items():
        if not re.fullmatch(r"[0-9a-f]{64}", str(digest)):
            raise GateError(f"invalid quarantine hash for {relative}")
        if _sha256(repo_root / relative) != digest:
            raise GateError(f"quarantine content drifted: {relative}")


def _count_pytest(output: str) -> int:
    return sum(
        int(count)
        for count, _ in re.findall(
            r"(\d+)\s+(passed|failed|skipped|xfailed|xpassed|error|errors)(?:\b|,)", output, re.I
        )
    )


def _count_node(output: str) -> int:
    matches = re.findall(r"^# tests\s+(\d+)\s*$", output, re.M)
    return int(matches[-1]) if matches else 0


def _playwright_counts(result_path: Path) -> tuple[int, dict[str, int]]:
    try:
        payload = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError(f"Playwright results.json is missing or malformed: {exc}") from exc
    stats = payload.get("stats")
    if not isinstance(stats, dict):
        raise GateError("Playwright results.json has no stats object")
    counts = {
        key: int(stats.get(key, 0))
        for key in ("expected", "unexpected", "flaky", "skipped")
    }
    return sum(counts.values()), counts


def _run(
    phase: str,
    command: list[str],
    artifact_dir: Path,
    repo_root: Path,
    *,
    env: dict[str, str] | None = None,
    timeout: int | None = None,
) -> tuple[subprocess.CompletedProcess[str], float]:
    started = time.monotonic()
    try:
        result = subprocess.run(
            command,
            cwd=repo_root,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout or DEFAULT_TIMEOUTS[phase],
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        output = _sanitize(exc.stdout or "", repo_root)
        (artifact_dir / f"{phase}.log").write_text(output, encoding="utf-8")
        raise GateError(f"{phase} timed out") from exc
    duration = time.monotonic() - started
    sanitized = _sanitize(result.stdout, repo_root)
    (artifact_dir / f"{phase}.log").write_text(sanitized, encoding="utf-8")
    return result, duration


def run_gate(inventory_path: Path, artifact_dir: Path, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    inventory_path = inventory_path.resolve()
    artifact_dir = artifact_dir.resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    inventory = load_inventory(inventory_path)
    validate_inventory(inventory, repo_root)

    commands = {
        "python": [sys.executable, "-m", "pytest", "-q", "--tb=short", *inventory["python"]["paths"]],
        "node": ["node", "--test", *inventory["node"]["paths"]],
        "playwright": [
            "node", "tests/e2e/run.mjs", "--", "--config", "tests/e2e/playwright.config.mjs",
            *inventory["playwright"]["paths"],
        ],
    }
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "ok": False,
        "inventory": inventory_path.relative_to(repo_root).as_posix(),
        "inventory_sha256": _sha256(inventory_path),
        "git": _git_identity(repo_root),
        "quarantine_sha256": inventory["quarantine_sha256"],
        "phases": {},
    }
    try:
        for phase in ("python", "node", "playwright"):
            env = os.environ.copy()
            if phase == "playwright":
                env["VIBECOMFY_E2E_ARTIFACT_DIR"] = str(artifact_dir / "e2e")
                env.setdefault("PYBIN", sys.executable)
                env["PATH"] = f"{Path(sys.executable).parent}{os.pathsep}{env.get('PATH', '')}"
            result, duration = _run(phase, commands[phase], artifact_dir, repo_root, env=env)
            output = result.stdout
            counts: dict[str, int] | None = None
            if phase == "python":
                collected = _count_pytest(output)
            elif phase == "node":
                collected = _count_node(output)
            else:
                launcher_path = artifact_dir / "e2e" / "launcher-result.json"
                try:
                    launcher = json.loads(launcher_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    raise GateError(f"launcher-result.json is missing or malformed: {exc}") from exc
                if launcher.get("ok") is not True or launcher.get("code") != "E2E_PASSED":
                    raise GateError(f"Playwright launcher did not report E2E_PASSED: {launcher.get('code')}")
                collected, counts = _playwright_counts(artifact_dir / "e2e" / "results.json")
                if any(counts[key] for key in ("unexpected", "flaky", "skipped")):
                    raise GateError(f"Playwright results are not clean: {counts}")
            phase_result = {
                "ok": result.returncode == 0,
                "exit_code": result.returncode,
                "duration_seconds": round(duration, 3),
                "collected": collected,
                "minimum_collected": inventory[phase]["minimum_collected"],
                "command": [_sanitize(part, repo_root) for part in commands[phase]],
                "log": f"{phase}.log",
            }
            if counts is not None:
                phase_result["playwright"] = counts
            manifest["phases"][phase] = phase_result
            if result.returncode != 0:
                raise GateError(f"{phase} exited with status {result.returncode}")
            if collected < inventory[phase]["minimum_collected"]:
                raise GateError(
                    f"{phase} collected {collected}, below locked minimum {inventory[phase]['minimum_collected']}"
                )
        manifest["ok"] = True
        manifest["outcome"] = "passed"
        return manifest
    except GateError as exc:
        manifest["outcome"] = "failed"
        manifest["remediation"] = _sanitize(str(exc), repo_root)
        raise
    finally:
        (artifact_dir / "manifest.json").write_text(
            f"{json.dumps(manifest, indent=2, sort_keys=True)}\n", encoding="utf-8"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", default="tests/corrective_gate_inventory.json")
    parser.add_argument("--artifact-dir", default="test-results/corrective-trust-gate")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = run_gate(REPO_ROOT / args.inventory, REPO_ROOT / args.artifact_dir)
    except GateError as exc:
        print(f"corrective trust gate failed: {_sanitize(str(exc), REPO_ROOT)}", file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, "manifest": manifest["outcome"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
