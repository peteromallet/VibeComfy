"""`vibecomfy test` CLI — snapshot / diff / verify subcommands (T7).

Drives the same canonicalizer that `scripts/regenerate_snapshots.py` uses, so
user recipes and curated ready-templates share one snapshot contract.
"""
from __future__ import annotations

import argparse
import json
import sys
from difflib import unified_diff
from pathlib import Path
from typing import Any


def _emit(payload: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))


def _stem_map() -> dict[str, str]:
    """Return the registered STEM_TO_READY_ID map from the regen script."""
    from importlib.util import module_from_spec, spec_from_file_location

    regen = Path(__file__).resolve().parents[2] / "scripts" / "regenerate_snapshots.py"
    if not regen.exists():
        return {}
    spec = spec_from_file_location("_regen_for_cli", regen)
    if spec is None or spec.loader is None:
        return {}
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "STEM_TO_READY_ID", {})


def _build_compiled_api(workflow_path: Path) -> dict[str, Any]:
    """Build a workflow from its module and return the compiled API dict."""
    from importlib.util import module_from_spec, spec_from_file_location

    spec = spec_from_file_location(f"_recipe_{workflow_path.stem}", workflow_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load recipe module: {workflow_path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "build"):
        raise RuntimeError(f"recipe {workflow_path} has no `build()` function")
    wf = module.build()
    return wf.compile("api")


def _snapshot_paths_for_stem(stem: str, repo_root: Path) -> dict[str, Path]:
    base = repo_root / "tests" / "snapshots"
    return {
        "api": base / f"{stem}.api.json",
        "class_types": base / f"{stem}.class_types.json",
        "widget_values": base / f"{stem}.widget_values.json",
    }


def _cmd_test_snapshot(args: argparse.Namespace) -> int:
    from vibecomfy.testing.snapshot import (
        canonicalize_api,
        canonicalize_class_types,
        canonicalize_widget_values,
    )

    path = Path(args.path).resolve()
    repo_root = Path(__file__).resolve().parents[2]
    stem_map = _stem_map()
    matched_stem = None
    for stem, ready_id in stem_map.items():
        candidate = repo_root / "ready_templates" / f"{ready_id}.py"
        if path == candidate.resolve():
            matched_stem = stem
            break

    try:
        api = _build_compiled_api(path)
    except Exception as exc:
        print(f"error: cannot build workflow at {path}: {exc}", file=sys.stderr)
        _emit({"ok": False, "error": str(exc), "path": str(path)}, args.json)
        return 2

    if matched_stem:
        targets = _snapshot_paths_for_stem(matched_stem, repo_root)
        for kind, target in targets.items():
            if target.exists() and not args.force:
                print(f"refusing to overwrite {target} (use --force)", file=sys.stderr)
                _emit({"ok": False, "error": "exists", "path": str(target)}, args.json)
                return 2
        targets["api"].write_text(canonicalize_api(api), encoding="utf-8")
        targets["class_types"].write_text(canonicalize_class_types(api), encoding="utf-8")
        targets["widget_values"].write_text(canonicalize_widget_values(api), encoding="utf-8")
        _emit({"ok": True, "stem": matched_stem, "wrote": [str(p) for p in targets.values()]}, args.json)
        if not args.json:
            print(f"wrote {matched_stem} snapshots")
        return 0

    sidecar = path.with_suffix(path.suffix + ".snapshot.json")
    if sidecar.exists() and not args.force:
        print(f"refusing to overwrite {sidecar} (use --force)", file=sys.stderr)
        _emit({"ok": False, "error": "exists", "path": str(sidecar)}, args.json)
        return 2
    sidecar.write_text(canonicalize_api(api), encoding="utf-8")
    _emit({"ok": True, "wrote": str(sidecar)}, args.json)
    if not args.json:
        print(f"wrote {sidecar}")
    return 0


def _cmd_test_diff(args: argparse.Namespace) -> int:
    from vibecomfy.testing.snapshot import canonicalize_api

    path = Path(args.path).resolve()
    try:
        api = _build_compiled_api(path)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        _emit({"ok": False, "error": str(exc)}, args.json)
        return 2
    sidecar = path.with_suffix(path.suffix + ".snapshot.json")
    if not sidecar.exists():
        print(f"no snapshot at {sidecar}", file=sys.stderr)
        _emit({"ok": False, "error": "no_snapshot", "path": str(sidecar)}, args.json)
        return 2
    expected = sidecar.read_text(encoding="utf-8")
    actual = canonicalize_api(api)
    if expected == actual:
        _emit({"ok": True, "drift": False}, args.json)
        return 0
    diff = list(
        unified_diff(
            expected.splitlines(keepends=True),
            actual.splitlines(keepends=True),
            fromfile=f"{sidecar} (committed)",
            tofile=f"{path} (rebuilt)",
        )
    )
    if not args.json:
        sys.stdout.writelines(diff)
    else:
        _emit({"ok": False, "drift": True, "diff": "".join(diff)}, args.json)
    return 1


def _cmd_test_verify(args: argparse.Namespace) -> int:
    from vibecomfy.testing.snapshot import (
        canonicalize_api,
        canonicalize_class_types,
        canonicalize_widget_values,
    )

    repo_root = Path(__file__).resolve().parents[2]
    input_path = Path(args.path).resolve()
    stem_map = _stem_map()
    rows: list[dict[str, Any]] = []
    ok = True

    if "ready_templates" in input_path.parts or input_path.name == "ready_templates":
        ready_root = repo_root / "ready_templates"
        for stem, ready_id in stem_map.items():
            template_path = ready_root / f"{ready_id}.py"
            if not template_path.exists():
                continue
            try:
                template_path.relative_to(input_path)
            except ValueError:
                continue
            try:
                api = _build_compiled_api(template_path)
                canon = {
                    "api": canonicalize_api(api),
                    "class_types": canonicalize_class_types(api),
                    "widget_values": canonicalize_widget_values(api),
                }
                targets = _snapshot_paths_for_stem(stem, repo_root)
                row_ok = True
                detail = []
                for kind, target in targets.items():
                    if not target.exists():
                        row_ok = False
                        detail.append(f"missing:{kind}")
                        continue
                    if target.read_text(encoding="utf-8") != canon[kind]:
                        row_ok = False
                        detail.append(f"drift:{kind}")
                rows.append({"stem": stem, "status": "ok" if row_ok else "drift", "detail": detail})
                if not row_ok:
                    ok = False
            except Exception as exc:
                rows.append({"stem": stem, "status": "drift", "detail": [f"error:{exc}"]})
                ok = False
    else:
        for recipe in sorted(input_path.glob("*.py")):
            sidecar = recipe.with_suffix(recipe.suffix + ".snapshot.json")
            if not sidecar.exists():
                continue
            try:
                api = _build_compiled_api(recipe)
                expected = sidecar.read_text(encoding="utf-8")
                actual = canonicalize_api(api)
                status = "ok" if expected == actual else "drift"
                rows.append({"recipe": str(recipe), "status": status})
                if status == "drift":
                    ok = False
            except Exception as exc:
                rows.append({"recipe": str(recipe), "status": "drift", "detail": [str(exc)]})
                ok = False

    if args.json:
        _emit({"ok": ok, "results": rows}, True)
    else:
        for row in rows:
            print(f"{row.get('status'):>5}: {row.get('stem', row.get('recipe'))}")
    return 0 if ok else 1


def register(subparsers: Any) -> None:
    test_parser = subparsers.add_parser("test", help="Snapshot user workflows: snapshot/diff/verify")
    test_subs = test_parser.add_subparsers(dest="test_action")

    snap = test_subs.add_parser("snapshot")
    snap.add_argument("path")
    snap.add_argument("--force", action="store_true")
    snap.add_argument("--json", action="store_true")
    snap.set_defaults(func=_cmd_test_snapshot)

    diff = test_subs.add_parser("diff")
    diff.add_argument("path")
    diff.add_argument("--json", action="store_true")
    diff.set_defaults(func=_cmd_test_diff)

    verify = test_subs.add_parser("verify")
    verify.add_argument("path")
    verify.add_argument("--json", action="store_true")
    verify.set_defaults(func=_cmd_test_verify)
