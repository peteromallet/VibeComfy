from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any

from vibecomfy.porting.object_info.consume import CACHE_DIR, cache_stats, get_class, list_classes
from vibecomfy.registry.models_loader import DOCUMENTED_NODE_PACK_GAPS, canonical_model_node_pack, load_registry
from vibecomfy.utils import find_repo_root


LEGACY_NODE_MODULES: dict[str, Path] = {
    "comfyui_kjnodes": Path("vibecomfy/nodes/comfyui_kjnodes.py"),
    "comfyui_ltxvideo": Path("vibecomfy/nodes/comfyui_ltxvideo.py"),
    "rgthree_comfy": Path("vibecomfy/nodes/rgthree_comfy.py"),
}
THIN_WRAPPER_MODULES: dict[str, str] = {
    "kjnodes": "vibecomfy.nodes.kjnodes",
    "ltxvideo": "vibecomfy.nodes.ltxvideo",
    "rgthree": "vibecomfy.nodes.rgthree",
}
REPRESENTATIVE_WRAPPER_SYMBOLS: dict[str, tuple[str, ...]] = {
    "vibecomfy.nodes.kjnodes": ("ImageResizeKJv2", "INTConstant"),
    "vibecomfy.nodes.ltxvideo": ("LTXVImgToVideoAdvanced", "LTXFloatToInt"),
    "vibecomfy.nodes.rgthree": ("Context_rgthree", "Power_Lora_Loader_rgthree"),
}
CHECK_ROOT_IGNORES = {".git", ".venv", "vendor", "docs", "__pycache__", ".claude", ".megaplan", "out", "tests"}
SCAN_EXCLUDED_PATHS = {
    Path("vibecomfy/checks.py"),
    Path("tests/test_check.py"),
}


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    status: str
    details: dict[str, Any]


@dataclass(frozen=True)
class CheckReport:
    ok: bool
    status: str
    schema_cache_class_count: int
    pack_file_count: int
    stub_pack_inventory: list[str]
    checks: list[CheckResult]


def run_checks(repo_root: Path | None = None) -> CheckReport:
    root = repo_root or find_repo_root()
    stub_pack_inventory = _stub_pack_inventory(root)
    schema_cache_class_count = len(list_classes())
    pack_file_count = len(_cache_pack_files())
    checks = [
        check_non_vendor_stale_legacy_references(root),
        check_thin_wrapper_import_smoke(),
        check_representative_wrapper_symbol_import_smoke(),
        check_model_registry_node_pack_validation(),
        check_schema_object_info_cache_access(),
        check_known_node_packs_usage_scan(root),
        check_legacy_file_presence(root),
    ]
    ok = all(check.ok for check in checks if check.status != "state")
    return CheckReport(
        ok=ok,
        status="ok" if ok else "error",
        schema_cache_class_count=schema_cache_class_count,
        pack_file_count=pack_file_count,
        stub_pack_inventory=stub_pack_inventory,
        checks=checks,
    )


def check_non_vendor_stale_legacy_references(repo_root: Path) -> CheckResult:
    matches = _scan_text_matches(repo_root, tuple(LEGACY_NODE_MODULES), suffixes={".py"})
    filtered = [
        match
        for match in matches
        if match["path"] not in {path.as_posix() for path in LEGACY_NODE_MODULES.values()}
    ]
    return CheckResult(
        name="non_vendor_stale_legacy_references",
        ok=not filtered,
        status="pass" if not filtered else "fail",
        details={"matches": filtered, "legacy_names": sorted(LEGACY_NODE_MODULES)},
    )


def check_thin_wrapper_import_smoke() -> CheckResult:
    modules: list[dict[str, Any]] = []
    failures: list[str] = []
    for stem, module_name in THIN_WRAPPER_MODULES.items():
        generated_name = f"vibecomfy.nodes._generated.{stem}"
        try:
            module = import_module(module_name)
            generated = import_module(generated_name)
            same_exports = list(getattr(module, "__all__", ())) == list(getattr(generated, "__all__", ()))
            if not same_exports:
                failures.append(module_name)
            modules.append(
                {
                    "module": module_name,
                    "generated_module": generated_name,
                    "export_count": len(getattr(module, "__all__", ())),
                    "exports_match_generated": same_exports,
                }
            )
        except Exception as exc:
            failures.append(module_name)
            modules.append({"module": module_name, "error": f"{type(exc).__name__}: {exc}"})
    return CheckResult(
        name="thin_wrapper_import_smoke",
        ok=not failures,
        status="pass" if not failures else "fail",
        details={"modules": modules, "failures": failures},
    )


def check_representative_wrapper_symbol_import_smoke() -> CheckResult:
    modules: list[dict[str, Any]] = []
    failures: list[str] = []
    for module_name, symbols in REPRESENTATIVE_WRAPPER_SYMBOLS.items():
        try:
            module = import_module(module_name)
            missing = [symbol for symbol in symbols if not hasattr(module, symbol)]
            row = {
                "module": module_name,
                "symbols": list(symbols),
                "missing": missing,
            }
            if missing:
                failures.append(module_name)
            modules.append(row)
        except Exception as exc:
            failures.append(module_name)
            modules.append({"module": module_name, "symbols": list(symbols), "error": f"{type(exc).__name__}: {exc}"})
    return CheckResult(
        name="representative_wrapper_symbol_import_smoke",
        ok=not failures,
        status="pass" if not failures else "fail",
        details={"modules": modules, "failures": failures},
    )


def check_model_registry_node_pack_validation() -> CheckResult:
    try:
        entries = load_registry()
    except Exception as exc:
        return CheckResult(
            name="model_registry_node_pack_validation",
            ok=False,
            status="fail",
            details={"error": f"{type(exc).__name__}: {exc}"},
        )
    target_names = [target.node_pack for entry in entries for target in entry.targets]
    documented_gap_targets = sorted({name for name in target_names if name in DOCUMENTED_NODE_PACK_GAPS})
    normalized_targets = sum(1 for name in target_names if canonical_model_node_pack(name) is not None)
    return CheckResult(
        name="model_registry_node_pack_validation",
        ok=True,
        status="pass",
        details={
            "entry_count": len(entries),
            "target_count": len(target_names),
            "normalized_target_count": normalized_targets,
            "documented_gap_targets": documented_gap_targets,
        },
    )


def check_schema_object_info_cache_access() -> CheckResult:
    classes = list_classes()
    class_count = len(classes)
    pack_files = _cache_pack_files()
    sample_class = classes[0] if classes else None
    sample_entry = get_class(sample_class) if sample_class is not None else None
    ok = class_count > 0 and bool(pack_files) and sample_entry is not None
    details = {
        "cache_stats": cache_stats(),
        "class_count": class_count,
        "pack_file_count": len(pack_files),
        "sample_class": sample_class,
        "sample_has_entry": sample_entry is not None,
    }
    if not ok:
        details["error"] = "object_info cache is missing classes, pack files, or a resolvable sample entry"
    return CheckResult(
        name="schema_object_info_cache_access",
        ok=ok,
        status="pass" if ok else "fail",
        details=details,
    )


def check_known_node_packs_usage_scan(repo_root: Path) -> CheckResult:
    token = "KNOWN" "_NODE_PACKS"
    matches = _scan_text_matches(repo_root, (token,), suffixes={".py"})
    return CheckResult(
        name="known_node_packs_usage_scan",
        ok=not matches,
        status="pass" if not matches else "fail",
        details={"matches": matches},
    )


def check_legacy_file_presence(repo_root: Path) -> CheckResult:
    present: list[dict[str, Any]] = []
    missing: list[str] = []
    for name, relative_path in LEGACY_NODE_MODULES.items():
        absolute_path = repo_root / relative_path
        if absolute_path.is_file():
            present.append(
                {
                    "name": name,
                    "path": _display_path(repo_root, absolute_path),
                    "size_bytes": absolute_path.stat().st_size,
                }
            )
        else:
            missing.append(relative_path.as_posix())
    return CheckResult(
        name="legacy_file_presence",
        ok=True,
        status="state",
        details={"present": present, "missing": missing},
    )


def _cache_pack_files() -> list[Path]:
    return sorted(path for path in CACHE_DIR.glob("*.json") if path.name != "index.json")


def _stub_pack_inventory(repo_root: Path) -> list[str]:
    inventory: list[str] = []
    nodes_root = repo_root / "vibecomfy" / "nodes"
    for stub_path in sorted(nodes_root.glob("*.pyi")):
        if stub_path.name == "__init__.pyi":
            continue
        text = stub_path.read_text(encoding="utf-8")
        if "from vibecomfy.nodes._generated." in text:
            inventory.append(stub_path.stem)
    return inventory


def _scan_text_matches(
    repo_root: Path,
    tokens: tuple[str, ...],
    *,
    suffixes: set[str] | None = None,
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for path in _iter_repo_files(repo_root):
        if suffixes is not None and path.suffix not in suffixes:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            token = next((candidate for candidate in tokens if candidate in line), None)
            if token is None:
                continue
            matches.append(
                {
                    "token": token,
                    "path": _display_path(repo_root, path),
                    "line": line_number,
                    "text": line.strip(),
                }
            )
    return matches


def _iter_repo_files(repo_root: Path):
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(repo_root)
        if any(part in CHECK_ROOT_IGNORES for part in relative.parts):
            continue
        if relative in SCAN_EXCLUDED_PATHS:
            continue
        yield path


def _display_path(repo_root: Path, path: Path) -> str:
    return path.relative_to(repo_root).as_posix()


__all__ = [
    "CheckReport",
    "CheckResult",
    "check_known_node_packs_usage_scan",
    "check_legacy_file_presence",
    "check_model_registry_node_pack_validation",
    "check_non_vendor_stale_legacy_references",
    "check_representative_wrapper_symbol_import_smoke",
    "check_schema_object_info_cache_access",
    "check_thin_wrapper_import_smoke",
    "run_checks",
]
