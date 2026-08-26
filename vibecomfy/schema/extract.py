"""Pack schema extraction — rungs 1, 2 & 3 of the on-demand node-schema ladder.

Factored out of ``tools/clone_and_extract_packs.py`` so the on-demand resolver
(:mod:`vibecomfy.schema.on_demand`) and the corpus builder share ONE extraction
core instead of two diverging parsers.

The ladder (each rung catches what the prior missed):

* **Rung 3** (``allow_embedded=True``): install ``comfyui=={version}`` into a
  throwaway venv and import real ``comfy``/``nodes`` in a child interpreter,
  load the pack's ``NODE_CLASS_MAPPINGS`` and call ``INPUT_TYPES()``. No
  HTTP server. No ``main.main``. Parent never imports ``comfy``.
* **Rung 2** (``allow_import=True``): spawn a subprocess that stubs the comfy
  imports, execs the pack's package, and calls ``cls.INPUT_TYPES()`` **at
  runtime**. Faithful to dynamic ``INPUT_TYPES`` (folder scans, computed lists,
  comfy-internal calls). Isolated to a child process, so a crashing or hostile
  pack fails the rung without taking down the caller. This is the rung that
  *executes third-party code* — the caller must opt in.
* **Rung 1** (always attempted): static AST parse of ``INPUT_TYPES`` return
  literals. No execution; catches the majority of packs but misses anything
  whose ``INPUT_TYPES`` is built at runtime.

All three rungs normalize to the ``object_info`` dict shape consumed by
:func:`vibecomfy.schema.provider._schema_from_object_info`, so a schema can be
handed straight to a :class:`~vibecomfy.schema.types.NodeSchema` via that helper.
"""
from __future__ import annotations

import ast
import json
import operator
import os
import shutil
import subprocess
import sys
import tempfile
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from vibecomfy.porting.object_info.pinned_venv import CommandRunner, provision_comfyui_venv

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
    method: str = ""  # "import" | "ast" | "embedded" | "" (nothing extracted)
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

    def _as_seq(value: Any) -> Any:
        # A class may inherit from the permissive stub machinery or declare
        # RETURN_TYPES as a bare scalar; iterating a string would emit one
        # bogus output per character. Only genuine sequences are output data.
        if isinstance(value, (list, tuple)):
            return value
        return ()

    return_types = _as_seq(attrs.get("RETURN_TYPES"))
    return_names = attrs.get("RETURN_NAMES")
    if not isinstance(return_names, (list, tuple)):
        return_names = None
    if return_names is None:
        return_names = return_types
    output_is_list = _as_seq(attrs.get("OUTPUT_IS_LIST"))

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
    # RRSYN-4: network/av stacks break extraction under interpreter-version
    # typing drift (aiohttp Generic[...] TypeError on 3.11.11) — INPUT_TYPES
    # extraction never needs a live transport, so stub them like the rest.
    "aiohttp", "websockets",
}


class StubModule(types.ModuleType):
    def __bool__(self):
        # Falsy so version-detection shims behave like their ImportError
        # fallbacks (e.g. stdlib ``copy``'s ``if PyStringMap is not None``).
        return False

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
        if name in {
            "get_full_path", "get_full_path_or_raise", "get_annotated_filepath",
            # RRSYN-4: path accessors leak into os.path.join during pack
            # import; they must return strings, not dummy classes.
            "get_input_directory", "get_output_directory",
            "get_temp_directory", "get_user_directory",
        }:
            return lambda *a, **k: ""
        if name in {"models_dir", "base_path", "output_directory", "input_directory"}:
            return ""
        if name.startswith("__"):
            return None
        return _dummy_class(name)


class _DummyMeta(type):
    def __getattr__(cls, name):
        # Class-level attribute access must stay permissive too: packs write
        # ``class Wrapper(torch.nn.Module)`` at import time, which reads the
        # attribute off the CLASS object, not an instance.
        return _dummy_class(f"{cls.__name__}.{name}")

    # RRSYN-4: packs iterate/membership-test/subscript stubbed classes at
    # import time (``for x in SomeEnum``, ``if X in Y``, ``M[k] = v``).
    # Benign empties keep the load going without fabricating node surfaces.

    def __iter__(cls):
        return iter(())

    def __contains__(cls, item):
        return False

    def __setitem__(cls, key, value):
        return None

    def __getitem__(cls, key):
        return _dummy_class(f"{cls.__name__}[{key!r}]")


def _dummy_class(name):
    # A permissive dummy: subclassable, instantiable, callable, and both
    # instance- and class-attribute-accessible.
    return _DummyMeta(
        name,
        (),
        {
            "__init__": lambda self, *a, **k: None,
            "__call__": lambda self, *a, **k: None,
            "__getattr__": lambda self, n: None,
        },
    )


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
        # Yield to reality: when a genuine module exists on disk (stdlib or an
        # installed dep), let the real loaders handle it. Shadowing live modules
        # corrupts their importers -- e.g. stubbing ``org.python.core`` makes
        # stdlib ``copy`` take its Jython branch and crash on import.
        try:
            if importlib.machinery.PathFinder.find_spec(fullname) is not None:
                return None
        except Exception:  # noqa: BLE001 - probing must never abort stubbing
            pass
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
    script = (scratch_dir / "_import_extract.py").resolve()
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
    # Packs may print ANSI banners/log lines on stdout before the JSON
    # payload; the JSON document is always the final print in the extractor.
    payload = result.stdout.strip()
    for line in reversed(payload.splitlines()):
        if line.lstrip().startswith("{"):
            payload = line
            break
    raw = json.loads(payload)
    return {name: payload_entry for name, payload_entry in raw.items() if isinstance(payload_entry, dict) and "_error" not in payload_entry}


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
        # RRSYN-4 fail-closed rule: a class whose INPUT_TYPES did not return
        # a real mapping (v3 comfy_api schema shim objects) was NOT faithfully
        # observed.  Excluding it records an honest gap; shipping a hollow
        # surface would let admission bless fields nobody captured.
        if not isinstance(payload.get("inputs"), dict):
            continue
        entries[class_name] = normalize_entry(
            class_name=class_name,
            raw_inputs=_sanitize_observed_inputs(payload.get("inputs")),
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


_EMBEDDED_EXTRACTOR = r"""
import os
import sys
import json
import importlib
import importlib.util
from pathlib import Path

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

pack_dir = Path(sys.argv[1])
pack_name = sys.argv[2]
_version = sys.argv[3]  # argv parity with the import extractor; unused here

try:
    import comfy
    import nodes
except Exception as exc:
    raise SystemExit(f"failed to import comfy/nodes: {exc}") from exc

parent_dir = str(pack_dir.parent)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
pack_str = str(pack_dir)
if pack_str not in sys.path:
    sys.path.insert(0, pack_str)

mod = None
try:
    mod = importlib.import_module(pack_name)
except Exception as exc:
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
            raise SystemExit(f"importlib.import_module failed ({exc}) and direct init load failed ({exc2})")
    else:
        raise SystemExit(f"pack has no __init__.py and import_module failed: {exc}")

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


def _default_embedded_timeout() -> int:
    try:
        val = int(os.environ.get("VIBECOMFY_EMBEDDED_TIMEOUT", "300"))
    except Exception:
        val = 300
    return val if val > 120 else 300


def _run_embedded_extractor(
    pack_dir: Path,
    pack_name: str,
    version: str,
    *,
    python_path: Path,
    timeout: int,
    runner: CommandRunner | None = None,
) -> dict[str, dict[str, Any]]:
    cmd = [str(python_path), "-c", _EMBEDDED_EXTRACTOR, str(pack_dir), pack_name, version]
    try:
        if runner is not None:
            result = runner(cmd)
        else:
            result = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"embedded extraction timed out after {timeout}s") from exc
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "embedded extraction failed")
    payload = result.stdout.strip()
    for line in reversed(payload.splitlines()):
        if line.lstrip().startswith("{"):
            payload = line
            break
    raw = json.loads(payload)
    return {name: entry for name, entry in raw.items() if isinstance(entry, dict) and "_error" not in entry}


def extract_by_embedded(
    pack_dir: Path,
    *,
    pack_name: str,
    version: str,
    only_classes: set[str] | None = None,
    comfy_version: str,
    timeout: int | None = None,
    scratch_dir: Path | None = None,
    runner: CommandRunner | None = None,
) -> tuple[dict[str, OrderedDict[str, Any]], str]:
    """Rung 3: install comfyui=={version} into a throwaway venv and import real comfy/nodes."""
    resolved_timeout = timeout if timeout is not None else _default_embedded_timeout()
    tmp_holder = None
    env_dir: Path | None = None
    try:
        if scratch_dir is None:
            tmp_holder = tempfile.TemporaryDirectory(prefix="vibecomfy-embedded-")
            env_dir = Path(tmp_holder.name) / "venv"
        else:
            scratch_path = Path(scratch_dir)
            scratch_path.mkdir(parents=True, exist_ok=True)
            env_dir = scratch_path / "venv"
        if runner is not None:
            provision_runner = runner
        else:
            def _timed_runner(cmd: Sequence[str]) -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    list(cmd),
                    check=True,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=resolved_timeout,
                )
            provision_runner = _timed_runner
        python_path = provision_comfyui_venv(env_dir, comfy_version, runner=provision_runner)
        raw = _run_embedded_extractor(
            pack_dir,
            pack_name,
            version,
            python_path=python_path,
            timeout=resolved_timeout,
            runner=runner,
        )
        entries: dict[str, OrderedDict[str, Any]] = {}
        for class_name, payload in raw.items():
            if only_classes is not None and class_name not in only_classes:
                continue
            if not isinstance(payload.get("inputs"), dict):
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
        return entries, "embedded"
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"embedded extraction timed out after {resolved_timeout}s") from exc
    finally:
        if tmp_holder is not None:
            tmp_holder.cleanup()
        elif env_dir is not None:
            shutil.rmtree(env_dir, ignore_errors=True)


def _sanitize_observed_inputs(raw_inputs: Any) -> Any:
    """Strip stub artifacts from an INPUT_TYPES mapping observed at runtime.

    RRSYN-4: under the auto-stub subprocess, folder-dependent combos come
    back empty or polluted with ``<class …>`` dummy artifacts, and INT/FLOAT
    bounds reference unresolvable sentinels.  These are NOT faithfully
    observed values.  Combos lose junk elements; when nothing resolvable
    remains they become the established ``["COMBO",
    {"unresolved_choices": True}]`` marker so the input stays authorable
    without fabricating options.  Unresolvable numeric bound keys are
    dropped rather than stringified.
    """
    if not isinstance(raw_inputs, dict):
        return raw_inputs

    def _is_artifact(value: Any) -> bool:
        return isinstance(value, str) and (
            value.startswith("<class") or value.startswith("<__main__")
        )

    def _clean_meta(meta: Any) -> Any:
        if not isinstance(meta, dict):
            return meta
        return {
            key: value
            for key, value in meta.items()
            if not _is_artifact(value)
        }

    cleaned_sections: dict[str, dict[str, Any]] = {}
    for section, group in raw_inputs.items():
        if not isinstance(group, dict):
            cleaned_sections[section] = group
            continue
        fixed_group: dict[str, Any] = {}
        for name, spec in group.items():
            if not (isinstance(spec, list) and spec):
                fixed_group[name] = spec
                continue
            head = spec[0]
            if isinstance(head, list):
                # A combo is faithfully captured only when EVERY option is a
                # plain string; anything else (boolean pairs, folder_paths
                # lists, dummy artifacts) becomes the established unresolved
                # marker instead of a fabricated option list.
                if head and all(isinstance(c, str) and not _is_artifact(c) for c in head):
                    fixed_group[name] = [head] + [_clean_meta(item) for item in spec[1:]]
                else:
                    fixed_group[name] = ["COMBO", {"unresolved_choices": True}]
            else:
                fixed_group[name] = [head] + [_clean_meta(item) for item in spec[1:]]
        cleaned_sections[section] = fixed_group
    return cleaned_sections


# --- Rung 1: static AST extraction (no execution) ----------------------------


class SafeEval:
    def __init__(self, env: dict[str, Any]):
        self.env = env

    _BIN_OPS: dict[type, Any] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }

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
        if isinstance(node, ast.BinOp):
            op = self._BIN_OPS.get(type(node.op))
            if op is not None:
                try:
                    return op(self.eval(node.left), self.eval(node.right))
                except Exception:
                    # Dynamic operand (e.g. ``"auto" + helper()``): degrade to
                    # an empty value instead of failing the whole extraction.
                    return []
        if isinstance(node, ast.IfExp):
            return self.eval(node.body) if self.eval(node.test) else self.eval(node.orelse)
        if isinstance(node, ast.DictComp):
            return {}
        if isinstance(node, ast.ListComp) or isinstance(node, ast.GeneratorExp):
            return []
        if isinstance(node, ast.SetComp):
            return set()
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

    def scoped_eval(self, node: ast.AST, local_env: dict[str, Any]) -> Any:
        """Evaluate *node* with *local_env* layered over the module-level env."""
        outer = self.env
        self.env = {**outer, **local_env}
        try:
            return self.eval(node)
        finally:
            self.env = outer


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


def _iter_fn_statements(stmts: list[ast.stmt]):
    """Yield statements in source order, descending into branch/loop bodies."""
    for stmt in stmts:
        yield stmt
        if isinstance(stmt, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith)):
            yield from _iter_fn_statements(stmt.body)
            yield from _iter_fn_statements(getattr(stmt, "orelse", []) or [])
        elif isinstance(stmt, ast.Try):
            yield from _iter_fn_statements(stmt.body)
            for handler in stmt.handlers:
                yield from _iter_fn_statements(handler.body)
            yield from _iter_fn_statements(getattr(stmt, "orelse", []) or [])


def input_types_return(class_def: ast.ClassDef, evaluator: SafeEval) -> Any:
    for stmt in class_def.body:
        if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) or stmt.name != "INPUT_TYPES":
            continue
        # Track simple local bindings (``choices = helper()`` etc.) so the
        # return statement can reference names assigned inside INPUT_TYPES.
        # Unresolvable values degrade to [] (empty combo choices), keeping the
        # input present instead of failing the whole class extraction.
        local_env: dict[str, Any] = {}
        for inner in _iter_fn_statements(stmt.body):
            if (
                isinstance(inner, ast.Assign)
                and len(inner.targets) == 1
                and isinstance(inner.targets[0], ast.Name)
                and isinstance(inner.value, ast.AST)
            ):
                try:
                    local_env[inner.targets[0].id] = evaluator.scoped_eval(inner.value, local_env)
                except Exception:
                    local_env[inner.targets[0].id] = []
                continue
            if isinstance(inner, ast.Return) and inner.value is not None:
                return evaluator.scoped_eval(inner.value, local_env)
    raise ValueError("missing literal INPUT_TYPES return")


def _node_mapping_aliases(tree: ast.Module, evaluator: SafeEval) -> dict[str, str]:
    """Statically resolve ``NODE_CLASS_MAPPINGS`` literals: exposed key -> class name.

    Live ``/object_info`` is keyed by the mapping key, which frequently differs
    from the Python class name (e.g. ``"easy int" -> Int``). Cache entries must
    use the exposed key or downstream lookups miss the class.
    """
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict)):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "NODE_CLASS_MAPPINGS" for t in node.targets):
            continue
        for key_node, value_node in zip(node.value.keys, node.value.values):
            if key_node is None:
                continue
            try:
                key = evaluator.eval(key_node)
                value = evaluator.eval(value_node)
            except Exception:
                continue
            if isinstance(key, str) and isinstance(value, str):
                aliases[key] = value.rsplit(".", 1)[-1]
    return aliases


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
    trees: list[tuple[Path, ast.Module, SafeEval]] = []
    aliases: dict[str, str] = {}
    for path in sorted(pack_dir.rglob("*.py")):
        if any(part.startswith(".") for part in path.relative_to(pack_dir).parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except UnicodeDecodeError:
            continue
        env = static_env(tree)
        evaluator = SafeEval(env)
        trees.append((path, tree, evaluator))
        aliases.update(_node_mapping_aliases(tree, evaluator))
    for path, tree, evaluator in trees:
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            served_keys = [node.name] + sorted(
                key for key, cls_name in aliases.items() if cls_name == node.name
            )
            if only_classes is not None:
                served_keys = [key for key in served_keys if key in only_classes]
                if not served_keys:
                    continue
            for entry_key in served_keys:
                try:
                    raw_inputs = input_types_return(node, evaluator)
                    attrs = class_attrs(node, evaluator)
                    entries[entry_key] = normalize_entry(
                        class_name=entry_key,
                        raw_inputs=raw_inputs,
                        pack_name=pack_name,
                        version=version,
                        python_module=f"{pack_name}.{path.relative_to(pack_dir).with_suffix('').as_posix().replace('/', '.')}",
                        attrs=attrs,
                    )
                except Exception as exc:
                    failures.append(f"{entry_key}: {exc}")
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
    allow_embedded: bool = False,
    comfy_version: str | None = None,
    embedded_timeout: int | None = None,
) -> ExtractResult:
    """Run the extraction ladder over a cloned pack source dir.

    Tries rung 2 (subprocess runtime INPUT_TYPES) when ``allow_import`` is set,
    falling back to rung 1 (static AST), then rung 3 (embedded comfy-as-library)
    when ``allow_embedded`` and no entries were produced. ``only_classes``
    restricts extraction to a known class set (``None`` extracts every resolvable
    class in the pack).
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

    if not entries and allow_embedded and pack_dir.is_dir():
        if not comfy_version:
            failures.append(
                "embedded: missing --comfy-version / VIBECOMFY_EMBEDDED_COMFY_VERSION (no comfy pin for rung 3)"
            )
        else:
            try:
                emb_entries, emb_method = extract_by_embedded(
                    pack_dir,
                    pack_name=pack_name,
                    version=version,
                    only_classes=only_classes,
                    comfy_version=comfy_version,
                    timeout=embedded_timeout,
                    scratch_dir=scratch_dir,
                )
                if emb_entries:
                    entries = emb_entries
                    method = emb_method
            except Exception as exc:  # noqa: BLE001
                failures.append(f"embedded: {exc}")

    return ExtractResult(entries=entries, method=method, failures=failures)
