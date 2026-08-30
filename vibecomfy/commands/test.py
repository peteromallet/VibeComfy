"""`vibecomfy test` CLI — snapshot / diff / verify subcommands (T7).

Drives the same canonicalizer that `python -m tools.regenerate_snapshots` uses, so
user recipes and curated ready-templates share one snapshot contract.
"""
from __future__ import annotations

import argparse
import json
import sys
import tomllib
from difflib import unified_diff
from pathlib import Path
from typing import Any

from vibecomfy.errors import CheckoutRequiredError
from vibecomfy.utils import find_repo_root


def _emit(payload: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))


def _stem_map() -> dict[str, str]:
    """Return the packaged curated snapshot registry."""
    from vibecomfy.testing.snapshot_registry import STEM_TO_READY_ID

    return STEM_TO_READY_ID


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


def _curated_repo_root(path: Path) -> Path | None:
    """Discover a checkout only when *path* is in its ready corpus."""
    if "ready_templates" not in path.parts:
        return None
    roots: list[Path] = []
    try:
        roots.append(find_repo_root())
    except CheckoutRequiredError:
        pass

    # An explicit absolute path may point into a checkout even when the
    # process CWD is neutral (the normal wheel/user-recipe case).  Inspect
    # only ancestors named ``ready_templates`` and require the VibeComfy
    # project marker, so an arbitrary user directory with that name remains
    # a user recipe root.
    for ancestor in (path, *path.parents):
        if ancestor.name != "ready_templates":
            continue
        manifest = ancestor.parent / "pyproject.toml"
        try:
            project = tomllib.loads(manifest.read_text(encoding="utf-8")).get("project", {})
        except (OSError, tomllib.TOMLDecodeError):
            continue
        if isinstance(project, dict) and project.get("name") == "vibecomfy":
            roots.append(ancestor.parent)

    for repo_root in roots:
        ready_root = (repo_root / "ready_templates").resolve()
        try:
            path.relative_to(ready_root)
        except ValueError:
            continue
        return repo_root
    return None


def _curated_template_stem(
    path: Path, repo_root: Path, stem_map: dict[str, str]
) -> str | None:
    """Return the canonical snapshot stem for one checkout-owned template."""
    for stem, ready_id in stem_map.items():
        candidate = repo_root / "ready_templates" / f"{ready_id}.py"
        if path == candidate.resolve():
            return stem
    return None


def _uncatalogued_curated_templates(
    input_path: Path, repo_root: Path, stem_map: dict[str, str]
) -> list[Path]:
    """List Python files in curated scope that have no canonical registry entry."""
    ready_root = (repo_root / "ready_templates").resolve()
    catalogued = {
        (repo_root / "ready_templates" / f"{ready_id}.py").resolve()
        for ready_id in stem_map.values()
    }
    candidates = [input_path] if input_path.is_file() else input_path.rglob("*.py")
    return sorted(
        path.resolve()
        for path in candidates
        if path.suffix == ".py"
        and path.resolve().is_relative_to(ready_root)
        and path.resolve() not in catalogued
    )


def _reject_uncatalogued_ready_template(path: Path, as_json: bool) -> int:
    message = f"ready template is not in the canonical snapshot registry: {path}"
    print(message, file=sys.stderr)
    _emit(
        {
            "ok": False,
            "error": "uncatalogued_ready_template",
            "path": str(path),
        },
        as_json,
    )
    return 2


def _build_user_compiled_api(workflow_path: Path) -> dict[str, Any]:
    """Build and apply directives for an explicitly supplied user recipe."""
    from vibecomfy.testing.snapshot import apply_directives, parse_directives

    api = _build_compiled_api(workflow_path)
    directives = parse_directives(workflow_path.read_text(encoding="utf-8"))
    return apply_directives(api, directives)


def _cmd_test_snapshot(args: argparse.Namespace) -> int:
    from vibecomfy.testing.snapshot import (
        canonicalize_api,
        canonicalize_class_types,
        canonicalize_widget_values,
    )

    path = Path(args.path).resolve()
    repo_root = _curated_repo_root(path)
    stem_map = _stem_map()
    matched_stem = (
        _curated_template_stem(path, repo_root, stem_map) if repo_root is not None else None
    )

    if repo_root is not None and matched_stem is None:
        return _reject_uncatalogued_ready_template(path, args.json)

    try:
        api = _build_compiled_api(path) if matched_stem else _build_user_compiled_api(path)
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
    repo_root = _curated_repo_root(path)
    stem_map = _stem_map()
    matched_stem = (
        _curated_template_stem(path, repo_root, stem_map) if repo_root is not None else None
    )
    if repo_root is not None and matched_stem is None:
        return _reject_uncatalogued_ready_template(path, args.json)
    try:
        api = _build_compiled_api(path) if matched_stem else _build_user_compiled_api(path)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        _emit({"ok": False, "error": str(exc)}, args.json)
        return 2
    sidecar = (
        _snapshot_paths_for_stem(matched_stem, repo_root)["api"]
        if matched_stem and repo_root is not None
        else path.with_suffix(path.suffix + ".snapshot.json")
    )
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

    input_path = Path(args.path).resolve()
    if not input_path.is_dir():
        message = f"verify target must be an existing directory: {input_path}"
        print(message, file=sys.stderr)
        _emit({"ok": False, "error": "invalid_target", "path": str(input_path)}, args.json)
        return 2

    repo_root = _curated_repo_root(input_path)
    stem_map = _stem_map()
    rows: list[dict[str, Any]] = []
    ok = True

    if repo_root is not None:
        uncatalogued = _uncatalogued_curated_templates(input_path, repo_root, stem_map)
        if uncatalogued:
            message = (
                "curated ready_templates scope contains files outside the canonical snapshot "
                f"registry: {', '.join(str(path) for path in uncatalogued)}"
            )
            print(message, file=sys.stderr)
            _emit(
                {
                    "ok": False,
                    "error": "uncatalogued_ready_template",
                    "path": str(input_path),
                    "uncatalogued": [str(path) for path in uncatalogued],
                },
                args.json,
            )
            return 2
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
                api = _build_user_compiled_api(recipe)
                expected = sidecar.read_text(encoding="utf-8")
                actual = canonicalize_api(api)
                status = "ok" if expected == actual else "drift"
                rows.append({"recipe": str(recipe), "status": status})
                if status == "drift":
                    ok = False
            except Exception as exc:
                rows.append({"recipe": str(recipe), "status": "drift", "detail": [str(exc)]})
                ok = False

    if not rows:
        message = f"no snapshots found in {input_path}"
        if not args.json:
            print(message, file=sys.stderr)
        _emit({"ok": False, "error": "no_snapshots", "path": str(input_path), "results": rows}, args.json)
        return 1

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
