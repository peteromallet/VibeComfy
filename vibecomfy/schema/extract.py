"""Pack schema extraction — rungs 1 & 2 of the on-demand node-schema ladder.

Factored out of ``tools/clone_and_extract_packs.py`` so the on-demand resolver
(:mod:`vibecomfy.schema.on_demand`) and the corpus builder share ONE extraction
core instead of two diverging parsers.

The ladder (each rung catches what the prior missed):

* **Rung 2** (``allow_import=True``): spawn a subprocess that stubs the comfy
  imports, execs the pack's package, and calls ``cls.INPUT_TYPES()`` **at
  runtime**. Faithful to dynamic ``INPUT_TYPES`` (folder scans, computed lists,
  comfy-internal calls). Isolated to a child process, so a crashing or hostile
  pack fails the rung without taking down the caller. This is the rung that
  *executes third-party code* — the caller must opt in.
* **Rung 1** (always attempted): static AST parse of ``INPUT_TYPES`` return
  literals. No execution; catches the majority of packs but misses anything
  whose ``INPUT_TYPES`` is built at runtime.

Both rungs normalize to the ``object_info`` dict shape consumed by
:func:`vibecomfy.schema.provider._schema_from_object_info`, so a schema can be
handed straight to a :class:`~vibecomfy.schema.types.NodeSchema` via that helper.
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Type strings that denote a slot-bound (link) input rather than a widget, used
# when deriving the object_info widget ordering.
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
class ExtractResult:
    """Outcome of running the extraction ladder over one pack source dir."""

    entries: dict[str, "OrderedDict[str, Any]"] = field(default_factory=dict)
    method: str = ""  # "import" | "ast" | "" (nothing extracted)
    failures: list[str] = field(default_factory=list)


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
    raw_inputs: Any,
    pack_name: str,
    version: str,
    python_module: str,
    attrs: dict[str, Any] | None = None,
) -> OrderedDict[str, Any]:
    """Build one ``object_info``-shaped entry from a parsed INPUT_TYPES payload."""
    attrs = attrs or {}
    inputs = normalize_inputs(raw_inputs)
    order = input_order(inputs)
    all_order = [name for section in ("required", "optional") for name in order.get(section, [])]

    return_types = attrs.get("RETURN_TYPES") or ()
    return_names = attrs.get("RETURN_NAMES")
    if return_names is None:
        return_names = return_types
    output_is_list = attrs.get("OUTPUT_IS_LIST") or ()

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

    category = attrs.get("CATEGORY") or ""
    function = attrs.get("FUNCTION") or class_name
    display_name = attrs.get("DESCRIPTION") or class_name

    return OrderedDict(
        (
            ("pack", pack_name),
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


# --- Rung 2: subprocess runtime extraction (executes third-party code) -------
# Runs in a child interpreter with the comfy + scientific stack AUTO-STUBBED via a
# sys.meta_path finder, so the pack's module-load succeeds and its real
# NODE_CLASS_MAPPINGS is exposed — then cls.INPUT_TYPES() actually runs, faithful
# to dynamic inputs. Failures are contained to the subprocess (non-zero exit ->
# rung skipped, fall back to AST).

_IMPORT_EXTRACTOR = r"""
import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import json
import sys
import types
from pathlib import Path

pack_dir = Path(sys.argv[1])
pack_name = sys.argv[2]
version = sys.argv[3]

# Module roots to auto-stub so a pack's module-load doesn't fail on missing
# heavy deps (comfy surface + the scientific stack). The pack itself is NEVER
# stubbed (it must import for real so its NODE_CLASS_MAPPINGS is populated).
STUB_ROOTS = {
    "folder_paths", "server", "nodes", "comfy_api", "comfy_execution",
    "comfyui", "comfy_extras", "app", "typing_extensions",
    "torch", "numpy", "cv2", "einops", "scipy", "skimage", "sklearn",
    "PIL", "transformers", "diffusers", "accelerate", "safetensors",
    "tokenizers", "soundfile", "librosa", "yaml", "spandrel", "onnxruntime",
    "timm", "imageio", "requests", "tqdm", "pytorch_lightning", "huggingface_hub",
}


class StubModule(types.ModuleType):
    def __getattr__(self, name):
        # Dunders a pack may read off a stubbed module (e.g. ``server.__file__``
        # for path math). Return benign defaults rather than raising, so a pack's
        # import-time path computation doesn't abort extraction.
        if name == "__file__":
            return ""
        if name == "__path__":
            return []
        if name in {"__version__", "__version_info__"}:
            return "0.0.0"
        if name in {"__all__", "__dict__"}:
            raise AttributeError(name)
        if name in {"get_filename_list", "get_folder_paths"}:
            return lambda *a, **k: []
        if name in {"get_full_path", "get_full_path_or_raise", "get_annotated_filepath"}:
            return lambda *a, **k: ""
        if name in {"models_dir", "base_path", "output_directory", "input_directory"}:
            return ""
        if name.startswith("__"):
            return None
        # A permissive dummy: callable, instantiable, and attribute-accessible.
        dummy = type(
            name,
            (),
            {
                "__init__": lambda self, *a, **k: None,
                "__call__": lambda self, *a, **k: None,
                "__getattr__": lambda self, n: None,
            },
        )
        setattr(self, name, dummy)
        return dummy


class _StubLoader(importlib.abc.Loader):
    def create_module(self, spec):
        mod = StubModule(spec.name)
        mod.__path__ = []  # mark as package so submodule imports resolve
        return mod

    def exec_module(self, module):
        return None


class AutoStubFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == pack_name or fullname.startswith(pack_name + "."):
            return None  # never stub the pack under test
        root = fullname.split(".", 1)[0]
        if root == "comfy" or root in STUB_ROOTS:
            return importlib.machinery.ModuleSpec(fullname, _StubLoader(), is_package=True)
        return None


sys.meta_path.insert(0, AutoStubFinder())


# Catch-all appended LAST: if no real importer can locate a module (a pack's
# pure-python dep we haven't enumerated -- piexif, rembg, etc.), stub it too so
# module-load keeps going and the pack's NODE_CLASS_MAPPINGS still populates.
class CatchAllStubFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == pack_name or fullname.startswith(pack_name + "."):
            return None  # never stub the pack under test or its submodules
        return importlib.machinery.ModuleSpec(fullname, _StubLoader(), is_package=True)


sys.meta_path.append(CatchAllStubFinder())

# Add the clone's parent to sys.path so importlib can find the package.
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
        try:
            out[class_name] = {
                "inputs": cls.INPUT_TYPES(),
                "return_types": getattr(cls, "RETURN_TYPES", ()),
                "return_names": getattr(cls, "RETURN_NAMES", None),
                "output_is_list": getattr(cls, "OUTPUT_IS_LIST", ()),
                "category": getattr(cls, "CATEGORY", ""),
                "function": getattr(cls, "FUNCTION", class_name),
                "module": getattr(cls, "__module__", ""),
            }
        except Exception as exc:
            out[class_name] = {"_error": str(exc)}
print(json.dumps(out, default=str))
"""


def _run_import_extractor(
    pack_dir: Path,
    pack_name: str,
    version: str,
    *,
    scratch_dir: Path,
    timeout: int,
) -> dict[str, dict[str, Any]]:
    """Run the stubbed subprocess extractor; return ``{class: payload}`` (empty on failure)."""
    script = scratch_dir / "_import_extract.py"
    script.write_text(_IMPORT_EXTRACTOR, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(script), str(pack_dir), pack_name, version],
        cwd=str(pack_dir.parent),
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "import extraction failed")
    raw = json.loads(result.stdout)
    return {name: payload for name, payload in raw.items() if isinstance(payload, dict) and "_error" not in payload}


def extract_by_import(
    pack_dir: Path,
    *,
    pack_name: str,
    version: str,
    only_classes: set[str] | None = None,
    scratch_dir: Path | None = None,
    timeout: int = 120,
) -> tuple[dict[str, OrderedDict[str, Any]], str]:
    """Rung 2: exec the pack in a stubbed subprocess and call INPUT_TYPES() at runtime."""
    scratch = scratch_dir or Path(tempfile.mkdtemp(prefix="vibecomfy_extract_"))
    raw = _run_import_extractor(pack_dir, pack_name, version, scratch_dir=scratch, timeout=timeout)
    entries: dict[str, OrderedDict[str, Any]] = {}
    for class_name, payload in raw.items():
        if only_classes is not None and class_name not in only_classes:
            continue
        entries[class_name] = normalize_entry(
            class_name=class_name,
            raw_inputs=payload.get("inputs"),
            pack_name=pack_name,
            version=version,
            python_module=payload.get("module") or pack_name,
            attrs={
                "RETURN_TYPES": payload.get("return_types"),
                "RETURN_NAMES": payload.get("return_names"),
                "OUTPUT_IS_LIST": payload.get("output_is_list"),
                "CATEGORY": payload.get("category"),
                "FUNCTION": payload.get("function"),
            },
        )
    return entries, "import"


# --- Rung 1: static AST extraction (no execution) ----------------------------


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


def extract_by_ast(
    pack_dir: Path,
    *,
    pack_name: str,
    version: str,
    only_classes: set[str] | None = None,
) -> tuple[dict[str, OrderedDict[str, Any]], str, list[str]]:
    """Rung 1: statically parse INPUT_TYPES return literals across the pack source."""
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
            if not isinstance(node, ast.ClassDef):
                continue
            if only_classes is not None and node.name not in only_classes:
                continue
            try:
                raw_inputs = input_types_return(node, evaluator)
                attrs = class_attrs(node, evaluator)
                entries[node.name] = normalize_entry(
                    class_name=node.name,
                    raw_inputs=raw_inputs,
                    pack_name=pack_name,
                    version=version,
                    python_module=f"{pack_name}.{path.relative_to(pack_dir).with_suffix('').as_posix().replace('/', '.')}",
                    attrs=attrs,
                )
            except Exception as exc:
                failures.append(f"{node.name}: {exc}")
    return entries, "ast", failures


def extract_pack_schemas(
    pack_dir: Path,
    *,
    pack_name: str,
    version: str = "on-demand",
    only_classes: set[str] | None = None,
    allow_import: bool = True,
    scratch_dir: Path | None = None,
    import_timeout: int = 120,
) -> ExtractResult:
    """Run the extraction ladder over a cloned pack source dir.

    Tries rung 2 (subprocess runtime INPUT_TYPES) when ``allow_import`` is set,
    falling back to rung 1 (static AST). ``only_classes`` restricts extraction to
    a known class set (``None`` extracts every resolvable class in the pack).
    """
    entries: dict[str, OrderedDict[str, Any]] = {}
    method = ""
    failures: list[str] = []

    if allow_import and pack_dir.is_dir():
        try:
            entries, method = extract_by_import(
                pack_dir,
                pack_name=pack_name,
                version=version,
                only_classes=only_classes,
                scratch_dir=scratch_dir,
                timeout=import_timeout,
            )
        except Exception as exc:  # noqa: BLE001 — a hostile/broken pack must not abort the ladder
            failures.append(f"import: {exc}")

    if not entries and pack_dir.is_dir():
        ast_entries, ast_method, ast_failures = extract_by_ast(
            pack_dir,
            pack_name=pack_name,
            version=version,
            only_classes=only_classes,
        )
        entries = ast_entries
        method = ast_method if entries else method
        failures.extend(ast_failures)

    return ExtractResult(entries=entries, method=method, failures=failures)
