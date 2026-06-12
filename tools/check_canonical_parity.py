"""Check ready-template canonical compile parity against one baseline file."""
from __future__ import annotations

import argparse
import hashlib
import json
import types
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from vibecomfy.testing.canonical import canonical_form
from vibecomfy.workflow import VibeWorkflow


# TODO(repo-root): migrate to vibecomfy.utils.find_repo_root() once this tool's
# script-mode import path is package-import-safe.
REPO_ROOT = Path(__file__).resolve().parents[1]
READY_ROOT = REPO_ROOT / "ready_templates"
DEFAULT_BASELINE = REPO_ROOT / "tests" / "fixtures" / "canonical_parity_baseline.json"
BASELINE_VERSION = 1


@dataclass(frozen=True)
class ParityRecord:
    id: str
    path: str
    sha256: str
    canonical_form: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "path": self.path,
            "sha256": self.sha256,
            "canonical_form": self.canonical_form,
        }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check canonical parity for non-manual ready templates.")
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--ready-root", type=Path, default=READY_ROOT)
    parser.add_argument("--update", action="store_true", help="Regenerate the canonical parity baseline.")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Check all current eligible templates. This is the default and kept for explicit CI readability.",
    )
    parser.add_argument("--json", action="store_true", help="Emit a JSON report.")
    args = parser.parse_args(argv)

    if args.update:
        payload = build_baseline(args.ready_root)
        args.baseline.parent.mkdir(parents=True, exist_ok=True)
        args.baseline.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
        report = {
            "ok": True,
            "updated": True,
            "baseline": str(args.baseline),
            "template_count": payload["template_count"],
        }
        _print_report(report, json_output=args.json)
        return 0

    report = check_baseline(args.baseline, ready_root=args.ready_root)
    _print_report(report, json_output=args.json)
    return 0 if report["ok"] else 1


def build_baseline(ready_root: Path = READY_ROOT) -> dict[str, Any]:
    records, skipped = collect_records_with_skips(ready_root)
    return {
        "version": BASELINE_VERSION,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "generated_from": "repo-only buildable non-manual ready_templates canonical compile output",
        "include_rule": "find ready_templates -type f -name '*.py' ! -name '_*' ! -name '__init__.py', exclude '# vibecomfy: manual', and include templates whose build() compiles to API",
        "template_count": len(records),
        "skipped_count": len(skipped),
        "skipped": skipped,
        "templates": [record.to_dict() for record in records],
    }


def check_baseline(baseline: Path = DEFAULT_BASELINE, *, ready_root: Path = READY_ROOT) -> dict[str, Any]:
    if not baseline.exists():
        return {
            "ok": False,
            "baseline": str(baseline),
            "errors": [f"missing baseline: {baseline}"],
            "missing": [],
            "extra": [],
            "mismatched": [],
        }

    expected_payload = json.loads(baseline.read_text(encoding="utf-8"))
    expected = {
        str(row["id"]): row
        for row in expected_payload.get("templates", [])
        if isinstance(row, dict) and row.get("id")
    }
    current_records, skipped = collect_records_with_skips(ready_root)
    current = {record.id: record for record in current_records}

    missing = sorted(set(expected) - set(current))
    extra = sorted(set(current) - set(expected))
    mismatched = [
        {
            "id": template_id,
            "expected_sha256": str(expected[template_id].get("sha256", "")),
            "actual_sha256": current[template_id].sha256,
            "path": current[template_id].path,
        }
        for template_id in sorted(set(expected) & set(current))
        if str(expected[template_id].get("sha256", "")) != current[template_id].sha256
    ]
    errors: list[str] = []
    errors.extend(f"missing eligible template: {template_id}" for template_id in missing)
    errors.extend(f"new eligible template missing from baseline: {template_id}" for template_id in extra)
    errors.extend(
        f"baseline template no longer compiles: {item['id']}: {item['error']}"
        for item in skipped
        if item["id"] in expected
    )
    errors.extend(
        f"canonical hash changed for {item['id']}: {item['expected_sha256']} -> {item['actual_sha256']}"
        for item in mismatched
    )
    return {
        "ok": not errors,
        "baseline": str(baseline),
        "template_count": len(current_records),
        "baseline_template_count": len(expected),
        "errors": errors,
        "missing": missing,
        "extra": extra,
        "mismatched": mismatched,
        "skipped": skipped,
    }


def collect_records(ready_root: Path = READY_ROOT) -> list[ParityRecord]:
    records, _skipped = collect_records_with_skips(ready_root)
    return records


def collect_records_with_skips(ready_root: Path = READY_ROOT) -> tuple[list[ParityRecord], list[dict[str, str]]]:
    records: list[ParityRecord] = []
    skipped: list[dict[str, str]] = []
    for path in _eligible_template_paths(ready_root):
        template_id = path.relative_to(ready_root).with_suffix("").as_posix()
        try:
            api = _compile_ready_template(path, template_id)
        except Exception as exc:  # noqa: BLE001 - diagnostics should report every non-buildable template.
            _reset_leaked_workflow_context()
            skipped.append(
                {
                    "id": template_id,
                    "path": path.relative_to(REPO_ROOT).as_posix() if path.is_relative_to(REPO_ROOT) else str(path),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue
        form = canonical_form(api)
        records.append(
            ParityRecord(
                id=template_id,
                path=path.relative_to(REPO_ROOT).as_posix() if path.is_relative_to(REPO_ROOT) else str(path),
                sha256=_canonical_sha256(form),
                canonical_form=form,
            )
        )
    return sorted(records, key=lambda record: record.id), sorted(skipped, key=lambda item: item["id"])


def _eligible_template_paths(ready_root: Path) -> list[Path]:
    if not ready_root.exists():
        return []
    paths = [
        path
        for path in ready_root.rglob("*.py")
        if path.name != "__init__.py" and not path.name.startswith("_") and not _is_manual_template(path)
    ]
    return sorted(paths, key=lambda path: path.relative_to(ready_root).as_posix())


def _is_manual_template(path: Path) -> bool:
    try:
        first_line = path.read_text(encoding="utf-8").splitlines()[0]
    except (OSError, IndexError):
        return False
    return first_line.strip() == "# vibecomfy: manual"


def _compile_ready_template(path: Path, template_id: str) -> dict[str, Any]:
    module = types.ModuleType(f"vibecomfy_canonical_parity_{template_id.replace('/', '_')}")
    module.__file__ = str(path)
    source = path.read_text(encoding="utf-8")
    exec(compile(source, str(path), "exec"), module.__dict__)  # noqa: S102 - trusted repo ready-template code.
    build = getattr(module, "build", None)
    if build is None:
        raise ValueError(f"Ready template {template_id} must define build()")
    workflow = build()
    if not isinstance(workflow, VibeWorkflow):
        raise TypeError(f"Ready template {template_id} build() must return VibeWorkflow, got {type(workflow).__name__}")
    return workflow.compile("api")


def _reset_leaked_workflow_context() -> None:
    """Keep one failed template from poisoning later template imports."""
    try:
        from vibecomfy.workflow_context import active_workflow, reset_workflow
    except Exception:
        return
    workflow = active_workflow()
    token = getattr(workflow, "_workflow_context_token", None) if workflow is not None else None
    if token is None:
        return
    try:
        reset_workflow(token)
    except Exception:
        return
    workflow._workflow_context_token = None


def _canonical_sha256(form: dict[str, Any]) -> str:
    rendered = json.dumps(form, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _print_report(report: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(report, indent=2, sort_keys=False))
        return
    if report["ok"]:
        action = "updated" if report.get("updated") else "passed"
        print(f"canonical parity {action}: {report.get('template_count', 0)} templates")
        return
    print("canonical parity failed")
    for error in report.get("errors", []):
        print(f"- {error}")


if __name__ == "__main__":
    raise SystemExit(main())
