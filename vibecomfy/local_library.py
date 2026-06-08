"""Local-library configuration: resolve custom_nodes and models paths.

Priority (highest to lowest):
  1. Environment variables (VIBECOMFY_CUSTOM_NODES_DIR, VIBECOMFY_MODELS_ROOT, COMFY_MODELS_ROOT)
  2. Repo-level TOML  (<repo_root>/vibecomfy.toml)
  3. Global TOML      (~/.vibecomfy/config.toml)

Sentinel values ``none`` / ``off`` / ``disabled`` (case-insensitive) in env vars
produce ``SlotState.DISABLED``.  Any other env value is treated as a path (env is
authoritative — validation is deferred to the write path).

Corrupt or unreadable TOML files are handled defensively: ``resolve()`` returns
``UNSET`` with ``source='error:...'`` and never raises.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path


_DISABLE_SENTINELS: frozenset[str] = frozenset({"none", "off", "disabled"})
_UNSET_SENTINEL = object()


# ── Public types ──────────────────────────────────────────────────────────────

class Slot(Enum):
    """Configurable local-library slots."""
    custom_nodes = "custom_nodes"
    models = "models"


class SlotState(Enum):
    """Tri-state for a resolved slot."""
    UNSET = auto()
    DISABLED = auto()
    SET = auto()


@dataclass(frozen=True)
class SlotResolution:
    """The resolved state of one local-library slot."""
    state: SlotState
    path: Path | None
    source: str  # "env:VIBECOMFY_CUSTOM_NODES_DIR", "repo", "global", "error:..."


# ── Config path helpers ───────────────────────────────────────────────────────

def _global_config_path() -> Path:
    return Path.home() / ".vibecomfy" / "config.toml"


def _repo_config_path(repo_root: Path) -> Path:
    return repo_root / "vibecomfy.toml"


# ── TOML reader ───────────────────────────────────────────────────────────────

class _TOMLReadError(Exception):
    """Raised internally when a TOML file exists but cannot be parsed."""


def _read_toml(path: Path) -> dict[str, object]:
    """Parse a TOML file.  Raises ``FileNotFoundError`` if missing,
    ``_TOMLReadError`` if corrupt/unreadable."""
    if not path.is_file():
        raise FileNotFoundError(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise _TOMLReadError(f"Cannot read {path}: {exc}") from exc
    try:
        data = tomllib.loads(raw)
    except Exception as exc:
        raise _TOMLReadError(f"Cannot parse {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise _TOMLReadError(f"TOML root must be a table: {path}")
    return data


def _get_toml_slot(data: dict[str, object], slot: Slot) -> str | None:
    """Extract a slot value from parsed TOML data, or None."""
    library = data.get("library")
    if not isinstance(library, dict):
        return None
    value = library.get(slot.value)
    if isinstance(value, bool):
        value = str(value).lower()
    if not isinstance(value, str):
        return None
    return value


# ── TOML writer (full-document round-trip) ────────────────────────────────────

def write_slot(slot: Slot, value: str, *, repo: Path | None = None) -> Path:
    """Persist *value* for *slot*.

    If *repo* is given, writes to ``<repo>/vibecomfy.toml``; otherwise
    writes to ``~/.vibecomfy/config.toml``.

    Uses a full-document read-modify-write cycle so unrelated top-level
    tables and non-library keys inside ``[library]`` are preserved.
    TOML comments are NOT preserved (documented limitation).
    """
    target = _repo_config_path(repo) if repo is not None else _global_config_path()

    try:
        existing = _read_toml(target)
    except (FileNotFoundError, _TOMLReadError):
        existing = None
    doc: dict[str, object] = {} if existing is None else dict(existing)

    library: dict[str, object] = {}
    raw_library = doc.get("library")
    if isinstance(raw_library, dict):
        library = dict(raw_library)

    library[slot.value] = value
    doc["library"] = library

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_format_toml(doc), encoding="utf-8")
    return target


def _format_toml(doc: dict[str, object]) -> str:
    """Serialize a TOML dict to a deterministic string."""
    lines: list[str] = []

    if "library" in doc:
        library = doc["library"]
        if isinstance(library, dict) and library:
            lines.append("[library]")
            for key in sorted(library):
                lines.append(f"{key} = {_toml_value(library[key])}")
            lines.append("")

    for table_name in sorted(doc):
        if table_name == "library":
            continue
        table = doc[table_name]
        if isinstance(table, dict) and table:
            lines.append(f"[{table_name}]")
            for key in sorted(table):
                lines.append(f"{key} = {_toml_value(table[key])}")
            lines.append("")

    return "\n".join(lines).rstrip("\n") + "\n"


def _toml_value(val: object) -> str:
    """Format a single TOML value (string, bool, number, or list)."""
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, str):
        escaped = val.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(val, list):
        return "[" + ", ".join(_toml_value(v) for v in val) + "]"
    return repr(val)


# ── Path validators ───────────────────────────────────────────────────────────

def validate_custom_nodes_dir(path: Path) -> str:
    """Validate a custom_nodes directory.

    Returns ``"ok"``, ``"looks_real"``, ``"missing"``, or ``"not_a_directory"``.
    """
    try:
        resolved = path.resolve(strict=False)
    except (OSError, RuntimeError):
        return "missing"
    if not resolved.exists():
        return "missing"
    if not resolved.is_dir():
        return "not_a_directory"
    try:
        children = list(resolved.iterdir())
    except (OSError, PermissionError):
        return "ok"
    if any(c.suffix == ".py" for c in children) or any(c.is_dir() for c in children):
        return "ok"
    return "looks_real"


def validate_models_dir(path: Path) -> str:
    """Validate a models directory.

    Returns ``"ok"``, ``"looks_real"``, ``"missing"``, or ``"not_a_directory"``.
    """
    try:
        resolved = path.resolve(strict=False)
    except (OSError, RuntimeError):
        return "missing"
    if not resolved.exists():
        return "missing"
    if not resolved.is_dir():
        return "not_a_directory"
    _KNOWN: frozenset[str] = frozenset({
        "checkpoints", "vae", "loras", "controlnet", "embeddings",
        "upscale_models", "clip_vision", "diffusion_models", "text_encoders",
        "unet", "configs",
    })
    try:
        children = {p.name for p in resolved.iterdir() if p.is_dir()}
    except (OSError, PermissionError):
        return "ok"
    return "ok" if children & _KNOWN else "looks_real"


# ── ComfyUI install detection ─────────────────────────────────────────────────

def detect_comfy_install() -> tuple[Path | None, Path | None]:
    """Probe for a ComfyUI installation.

    Returns ``(comfy_root, models_dir)`` — each may be None.
    Probes: COMFYUI_PATH env, comfy package location, ~/ComfyUI, CWD.
    """
    if env_path := os.environ.get("COMFYUI_PATH"):
        p = Path(env_path)
        if p.is_dir():
            return (p, p / "models" if (p / "models").is_dir() else None)

    try:
        import comfy
        comfy_dir = Path(comfy.__file__).resolve().parent
        root = comfy_dir.parent
        return (root, root / "models" if (root / "models").is_dir() else None)
    except Exception:
        pass

    home_comfy = Path.home() / "ComfyUI"
    if home_comfy.is_dir():
        return (home_comfy, home_comfy / "models" if (home_comfy / "models").is_dir() else None)

    cwd = Path.cwd()
    if (cwd / "custom_nodes").is_dir() or (cwd / "models").is_dir():
        return (cwd, cwd / "models" if (cwd / "models").is_dir() else None)

    return (None, None)


# ── Resolution engine ─────────────────────────────────────────────────────────

_SLOT_ENV_VARS: dict[Slot, tuple[str, ...]] = {
    Slot.custom_nodes: ("VIBECOMFY_CUSTOM_NODES_DIR",),
    Slot.models: ("VIBECOMFY_MODELS_ROOT", "COMFY_MODELS_ROOT"),
}


def _resolve_env(slot: Slot) -> tuple[object, str]:
    """Check env vars.  Returns ``(Path|False|_UNSET_SENTINEL, source)``."""
    for env_name in _SLOT_ENV_VARS.get(slot, ()):
        raw = os.environ.get(env_name)
        if raw is None:
            continue
        if raw.strip().lower() in _DISABLE_SENTINELS:
            return (False, f"env:{env_name}")
        return (Path(raw.strip()), f"env:{env_name}")
    return (_UNSET_SENTINEL, "")


def _resolve_toml(slot: Slot, repo_root: Path | None) -> tuple[object, str]:
    """Check repo then global TOML.  May raise ``_TOMLReadError`` for
    corrupt files (caught by ``resolve()`` and surfaced as ``error:...``)."""
    # Repo first
    if repo_root is not None:
        try:
            data = _read_toml(_repo_config_path(repo_root))
        except FileNotFoundError:
            pass
        else:
            val = _get_toml_slot(data, slot)
            if val is not None:
                if val.strip().lower() in _DISABLE_SENTINELS:
                    return (False, "repo")
                return (Path(val.strip()), "repo")

    # Global
    try:
        data = _read_toml(_global_config_path())
    except FileNotFoundError:
        pass
    else:
        val = _get_toml_slot(data, slot)
        if val is not None:
            if val.strip().lower() in _DISABLE_SENTINELS:
                return (False, "global")
            return (Path(val.strip()), "global")

    return (_UNSET_SENTINEL, "")


def resolve(slot: Slot, *, repo_root: Path | None = None) -> SlotResolution:
    """Resolve *slot* using env → repo → global precedence.

    Never raises — returns ``UNSET`` with ``source='error:...'`` on failure.
    """
    try:
        value, source = _resolve_env(slot)
        if value is not _UNSET_SENTINEL:
            if value is False:
                return SlotResolution(SlotState.DISABLED, None, source)
            return SlotResolution(SlotState.SET, Path(value).resolve(), source)  # type: ignore[arg-type]

        value, source = _resolve_toml(slot, repo_root)
        if value is not _UNSET_SENTINEL:
            if value is False:
                return SlotResolution(SlotState.DISABLED, None, source)
            return SlotResolution(SlotState.SET, Path(value).resolve(), source)  # type: ignore[arg-type]

        return SlotResolution(SlotState.UNSET, None, "default")
    except Exception as exc:
        return SlotResolution(SlotState.UNSET, None, f"error:{exc}")


# ── Convenience helpers ───────────────────────────────────────────────────────

def resolved_path(slot: Slot, *, repo_root: Path | None = None) -> Path | None:
    """Return the resolved path when SET, or None."""
    r = resolve(slot, repo_root=repo_root)
    return r.path if r.state is SlotState.SET else None


# ── Test hook ─────────────────────────────────────────────────────────────────

def _clear_cache() -> None:
    """Clear internal caches for test isolation (future-proof hook)."""


# ── Public API ────────────────────────────────────────────────────────────────

__all__ = [
    "Slot",
    "SlotState",
    "SlotResolution",
    "detect_comfy_install",
    "resolve",
    "resolved_path",
    "validate_custom_nodes_dir",
    "validate_models_dir",
    "write_slot",
]
