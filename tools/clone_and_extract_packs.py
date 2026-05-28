"""Clone missing custom-node packs and extract object_info schemas.

This is a one-shot ETL helper for augmenting
``vibecomfy/porting/cache/object_info`` from the registry in
``vibecomfy.node_packs``.  It intentionally avoids installing package
dependencies unless a future caller chooses to extend it; the direct import
path uses local stubs, and the fallback path statically reads class schemas.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import shutil
import subprocess
import sys
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vibecomfy.node_packs import CustomNodePack, get_known_node_packs


# TODO(repo-root): migrate to vibecomfy.utils.find_repo_root() once this tool's
# script-mode import path is package-import-safe.
ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "vibecomfy" / "porting" / "cache" / "object_info"
INDEX_PATH = CACHE_DIR / "index.json"
TMP_ROOT = ROOT / ".tmp_packs"

LINK_ONLY_TYPES = {
    "MODEL",
    "CLIP",
    "VAE",
    "IMAGE",
    "LATENT",
    "CONDITIONING",
    "MASK",
    "AUDIO",
    "VIDEO",
    "hidden",
}


@dataclass
class PackReport:
    name: str
    repo: str
    cloned: bool = False
    sha7: str = ""
    method: str = ""
    class_count: int = 0
    cache_file: str = ""
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def run(cmd: list[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def load_index() -> dict[str, str]:
    if not INDEX_PATH.exists():
        return {}
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def missing_packs(index: dict[str, str]) -> list[CustomNodePack]:
    missing: list[CustomNodePack] = []
    known = set(index)
    for pack in get_known_node_packs():
        if not set(pack.classes).issubset(known):
            missing.append(pack)
    return missing


def clone_pack(pack: CustomNodePack, report: PackReport) -> Path | None:
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    dest = TMP_ROOT / pack.name
    if dest.exists():
        shutil.rmtree(dest)
    result = run(["git", "clone", "--depth", "1", pack.repo, str(dest)], check=False)
    if result.returncode != 0:
        report.failures.append(result.stderr.strip() or result.stdout.strip() or "git clone failed")
        return None
    report.cloned = True
    sha = run(["git", "rev-parse", "--short", "HEAD"], cwd=dest).stdout.strip()
    report.sha7 = sha
    return dest


def jsonable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, tuple):
        return [jsonable(item) for item in value]
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(jsonable(key)): jsonable(val) for key, val in value.items()}
    if isinstance(value, set):
        return [jsonable(item) for item in sorted(value, key=str)]
    return str(value)


def normalize_inputs(raw_inputs: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(raw_inputs, dict):
        return {}
    inputs: dict[str, dict[str, Any]] = {}
    for section, values in raw_inputs.items():
        if section == "hidden" or not isinstance(values, dict):
            continue
        inputs[section] = OrderedDict()
        for name, spec in values.items():
            inputs[section][str(name)] = jsonable(spec)
    return inputs


def input_order(inputs: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    return OrderedDict((section, list(values)) for section, values in inputs.items())


def widget_order(inputs: dict[str, dict[str, Any]], ordered: list[str]) -> list[str | None]:
    out: list[str | None] = []
    for name in ordered:
        spec = None
        for section in ("required", "optional"):
            if name in inputs.get(section, {}):
                spec = inputs[section][name]
                break
        comfy_type = spec[0] if isinstance(spec, list) and spec else None
        if isinstance(comfy_type, list):
            out.append(name)
        elif isinstance(comfy_type, str) and comfy_type not in LINK_ONLY_TYPES:
            out.append(name)
        else:
            out.append(None)
    return out


def normalize_entry(
    *,
    class_name: str,
    cls_obj: Any | None,
    raw_inputs: Any,
    pack: CustomNodePack,
    version: str,
    python_module: str,
    attrs: dict[str, Any] | None = None,
) -> OrderedDict[str, Any]:
    attrs = attrs or {}
    inputs = normalize_inputs(raw_inputs)
    order = input_order(inputs)
    all_order = [name for section in ("required", "optional") for name in order.get(section, [])]

    return_types = attrs.get("RETURN_TYPES")
    if return_types is None and cls_obj is not None:
        return_types = getattr(cls_obj, "RETURN_TYPES", ())
    return_names = attrs.get("RETURN_NAMES")
    if return_names is None and cls_obj is not None:
        return_names = getattr(cls_obj, "RETURN_NAMES", None)
    if return_names is None:
        return_names = return_types
    output_is_list = attrs.get("OUTPUT_IS_LIST")
    if output_is_list is None and cls_obj is not None:
        output_is_list = getattr(cls_obj, "OUTPUT_IS_LIST", [])

    return_types = list(jsonable(return_types or ()))
    return_names = list(jsonable(return_names or ()))
    output_is_list = list(jsonable(output_is_list or ()))
    outputs = []
    for i, output_type in enumerate(return_types):
        outputs.append(
            {
                "type": str(output_type),
                "name": str(return_names[i]) if i < len(return_names) else str(output_type),
                "is_list": bool(output_is_list[i]) if i < len(output_is_list) else False,
            }
        )

    category = attrs.get("CATEGORY")
    if category is None and cls_obj is not None:
        category = getattr(cls_obj, "CATEGORY", "")
    function = attrs.get("FUNCTION")
    if function is None and cls_obj is not None:
        function = getattr(cls_obj, "FUNCTION", class_name)
    display_name = attrs.get("DESCRIPTION")
    if display_name is None:
        display_name = class_name

    return OrderedDict(
        (
            ("pack", pack.name),
            ("pack_version", version),
            ("python_module", python_module),
            ("category", str(category or "")),
            ("name", class_name),
            ("display_name", str(display_name or class_name)),
            ("description", ""),
            ("inputs", inputs),
            ("input_order", order),
            ("input_order_all", all_order),
            ("object_info_widget_order", widget_order(inputs, all_order)),
            ("outputs", outputs),
            ("function", str(function or class_name)),
        )
    )


IMPORT_EXTRACTOR = r"""
import importlib
import importlib.util
import json
import sys
import types
from pathlib import Path

pack_dir = Path(sys.argv[1])
pack_name = sys.argv[2]
version = sys.argv[3]

class StubModule(types.ModuleType):
    def __getattr__(self, name):
        if name in {"get_filename_list", "get_folder_paths"}:
            return lambda *a, **k: []
        if name in {"get_full_path", "get_full_path_or_raise", "get_annotated_filepath"}:
            return lambda *a, **k: ""
        if name in {"models_dir", "base_path", "output_directory", "input_directory"}:
            return ""
        dummy = type(name, (), {"__init__": lambda self, *a, **k: None})
        setattr(self, name, dummy)
        return dummy

def stub(name):
    mod = StubModule(name)
    sys.modules[name] = mod
    return mod

for name in [
    "folder_paths", "comfy", "comfy.utils", "comfy.model_management",
    "comfy.sd", "comfy.samplers", "comfy.sample", "comfy.controlnet",
    "comfy.clip_vision", "comfy_extras", "comfy_extras.nodes_audio",
    "server", "nodes",
]:
    if name not in sys.modules:
        stub(name)

# Add the clone's parent to sys.path so importlib can find the package
parent_dir = str(pack_dir.parent)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Try importlib.import_module first (handles relative imports like from .utils import ...)
mod = None
try:
    mod = importlib.import_module(pack_name)
except Exception as exc:
    # Fallback: direct __init__.py loading (for packs that don't use relative imports)
    init = pack_dir / "__init__.py"
    if init.exists():
        spec = importlib.util.spec_from_file_location(
            "_vibecomfy_pack_under_test", init, submodule_search_locations=[str(pack_dir)]
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules["_vibecomfy_pack_under_test"] = mod
        try:
            spec.loader.exec_module(mod)
        except Exception as exc2:
            raise RuntimeError(f"importlib.import_module failed ({exc}) and direct init load failed ({exc2})")
    else:
        raise RuntimeError(f"pack has no __init__.py and import_module failed: {exc}")

mappings = getattr(mod, "NODE_CLASS_MAPPINGS", {})
out = {}
for class_name, cls in mappings.items():
    if hasattr(cls, "INPUT_TYPES"):
        out[class_name] = {
            "inputs": cls.INPUT_TYPES(),
            "return_types": getattr(cls, "RETURN_TYPES", ()),
            "return_names": getattr(cls, "RETURN_NAMES", None),
            "output_is_list": getattr(cls, "OUTPUT_IS_LIST", ()),
            "category": getattr(cls, "CATEGORY", ""),
            "function": getattr(cls, "FUNCTION", class_name),
            "module": getattr(cls, "__module__", ""),
        }
print(json.dumps(out, default=str))
"""


def extract_by_import(pack_dir: Path, pack: CustomNodePack, version: str) -> tuple[dict[str, OrderedDict[str, Any]], str]:
    script = TMP_ROOT / "_import_extract.py"
    script.write_text(IMPORT_EXTRACTOR, encoding="utf-8")
    result = run([sys.executable, str(script), str(pack_dir), pack.name, version], cwd=ROOT, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    raw = json.loads(result.stdout)
    entries: dict[str, OrderedDict[str, Any]] = {}
    for class_name, payload in raw.items():
        if class_name not in pack.classes:
            continue
        entries[class_name] = normalize_entry(
            class_name=class_name,
            cls_obj=None,
            raw_inputs=payload.get("inputs"),
            pack=pack,
            version=version,
            python_module=payload.get("module") or pack.name,
            attrs={
                "RETURN_TYPES": payload.get("return_types"),
                "RETURN_NAMES": payload.get("return_names"),
                "OUTPUT_IS_LIST": payload.get("output_is_list"),
                "CATEGORY": payload.get("category"),
                "FUNCTION": payload.get("function"),
            },
        )
    return entries, "import"


class SafeEval:
    def __init__(self, env: dict[str, Any]):
        self.env = env

    def eval(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.List):
            return [self.eval(item) for item in node.elts]
        if isinstance(node, ast.Tuple):
            return tuple(self.eval(item) for item in node.elts)
        if isinstance(node, ast.Set):
            return {self.eval(item) for item in node.elts}
        if isinstance(node, ast.Dict):
            return {self.eval(k): self.eval(v) for k, v in zip(node.keys, node.values) if k is not None}
        if isinstance(node, ast.Name):
            if node.id in self.env:
                return self.env[node.id]
            return node.id
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -self.eval(node.operand)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return self.eval(node.left) + self.eval(node.right)
        if isinstance(node, ast.Attribute):
            return node.attr
        if isinstance(node, ast.Subscript):
            value = self.eval(node.value)
            slc = self.eval(node.slice)
            try:
                return value[slc]
            except Exception:
                return value
        if isinstance(node, ast.Call):
            func_name = dotted_name(node.func)
            if func_name and any(token in func_name for token in ("get_filename_list", "get_folder_paths", "listdir")):
                return []
            if func_name and func_name.endswith(("join", "basename")):
                return ""
            return []
        raise ValueError(f"unsupported AST node: {type(node).__name__}")


def dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = dotted_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def static_env(tree: ast.Module) -> dict[str, Any]:
    env: dict[str, Any] = {}
    evaluator = SafeEval(env)
    for stmt in tree.body:
        if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
            continue
        target = stmt.targets[0]
        if not isinstance(target, ast.Name):
            continue
        try:
            env[target.id] = evaluator.eval(stmt.value)
        except Exception:
            continue
    return env


def class_attrs(class_def: ast.ClassDef, evaluator: SafeEval) -> dict[str, Any]:
    attrs: dict[str, Any] = {}
    for stmt in class_def.body:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            name = stmt.targets[0].id
            if name in {"RETURN_TYPES", "RETURN_NAMES", "OUTPUT_IS_LIST", "CATEGORY", "FUNCTION", "DESCRIPTION"}:
                try:
                    attrs[name] = evaluator.eval(stmt.value)
                except Exception:
                    pass
    return attrs


def input_types_return(class_def: ast.ClassDef, evaluator: SafeEval) -> Any:
    for stmt in class_def.body:
        if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) or stmt.name != "INPUT_TYPES":
            continue
        for inner in ast.walk(stmt):
            if isinstance(inner, ast.Return) and inner.value is not None:
                return evaluator.eval(inner.value)
    raise ValueError("missing literal INPUT_TYPES return")


def extract_by_ast(pack_dir: Path, pack: CustomNodePack, version: str) -> tuple[dict[str, OrderedDict[str, Any]], str, list[str]]:
    entries: dict[str, OrderedDict[str, Any]] = {}
    failures: list[str] = []
    for path in sorted(pack_dir.rglob("*.py")):
        if any(part.startswith(".") for part in path.relative_to(pack_dir).parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except UnicodeDecodeError:
            continue
        env = static_env(tree)
        evaluator = SafeEval(env)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef) or node.name not in pack.classes:
                continue
            try:
                raw_inputs = input_types_return(node, evaluator)
                attrs = class_attrs(node, evaluator)
                entries[node.name] = normalize_entry(
                    class_name=node.name,
                    cls_obj=None,
                    raw_inputs=raw_inputs,
                    pack=pack,
                    version=version,
                    python_module=f"{pack.name}.{path.relative_to(pack_dir).with_suffix('').as_posix().replace('/', '.')}",
                    attrs=attrs,
                )
            except Exception as exc:
                failures.append(f"{node.name}: {exc}")
    unresolved = sorted(set(pack.classes) - set(entries))
    failures.extend(f"{name}: not found" for name in unresolved)
    return entries, "ast", failures


def write_cache(pack: CustomNodePack, version: str, entries: dict[str, OrderedDict[str, Any]], index: dict[str, str], report: PackReport) -> None:
    filename = f"{pack.name}@{version}.json"
    path = CACHE_DIR / filename
    ordered = OrderedDict((name, entries[name]) for name in sorted(entries))
    path.write_text(json.dumps(ordered, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    report.cache_file = str(path.relative_to(ROOT))

    for class_name in sorted(entries):
        existing = index.get(class_name)
        if existing and existing != filename:
            report.warnings.append(f"{class_name}: index remapped from {existing} to {filename}")
        index[class_name] = filename


def process_pack(pack: CustomNodePack, index: dict[str, str]) -> PackReport:
    report = PackReport(name=pack.name, repo=pack.repo)
    pack_dir = clone_pack(pack, report)
    if pack_dir is None:
        return report

    version = f"local-{report.sha7}"
    try:
        entries, method = extract_by_import(pack_dir, pack, version)
    except Exception as exc:
        report.warnings.append(f"import failed: {exc}")
        entries, method, failures = extract_by_ast(pack_dir, pack, version)
        report.failures.extend(failures)

    if not entries:
        if not report.failures:
            report.failures.append("no classes extracted")
        return report

    report.method = method
    report.class_count = len(entries)
    write_cache(pack, version, entries, index, report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", action="append", help="Only process the named pack; can be repeated.")
    parser.add_argument("--keep", action="store_true", help="Keep .tmp_packs clones after extraction.")
    return parser.parse_args()


def main() -> int:
    os.chdir(ROOT)
    args = parse_args()
    index = load_index()
    original_index = dict(index)
    selected = missing_packs(index)
    if args.pack:
        wanted = set(args.pack)
        selected = [pack for pack in get_known_node_packs() if pack.name in wanted]

    print(f"Missing packs: {', '.join(pack.name for pack in selected) or '(none)'}")
    reports = [process_pack(pack, index) for pack in selected]
    if index != original_index:
        INDEX_PATH.write_text(json.dumps(dict(sorted(index.items())), indent=2) + "\n", encoding="utf-8")

    print("\nReport:")
    for report in reports:
        print(f"- {report.name}: {report.class_count} classes, method={report.method or 'none'}")
        if report.cache_file:
            print(f"  cache: {report.cache_file}")
        if report.warnings:
            print("  warnings:")
            for warning in report.warnings:
                print(f"    - {warning}")
        if report.failures:
            print("  failures:")
            for failure in report.failures:
                print(f"    - {failure}")

    if not args.keep:
        script = TMP_ROOT / "_import_extract.py"
        if script.exists():
            script.unlink()

    return 1 if any(report.failures and report.class_count == 0 for report in reports) else 0


if __name__ == "__main__":
    raise SystemExit(main())
