"""Optional ComfyUI backend adoption hook (M2 Step 7, SD2).

This module is an OPTIONAL optimization, never a hard dependency. M2's identity
derivation is pure-Python (see ``vibecomfy.porting.identity.scope.sg_key``); nothing in
the M2 feature set requires a real ComfyUI node catalog. ``ensure_nodes()`` lets
a caller *adopt* the real catalog when it happens to be available — either via
the ``[comfy]`` optional-dependency extra or the vendored ``vendor/ComfyUI``
submodule — and otherwise returns ``False`` so callers fall back to the
pure-Python path without error.

The import is guarded by ``try/except`` and memoized so it is attempted at most
once per process. When the extra is not installed AND the submodule is
uninitialized, ``ensure_nodes()`` returns ``False`` and never raises.


Compatibility matrix (S1 oracle-durability)
-------------------------------------------
Also provides a ``version_matrix.json`` loader and vendored-commit reader so
the S1 skew fence can compare the running ComfyUI against the pinned oracle
without importing the full dependency tree. ``load_version_matrix()`` returns
a typed ``VersionMatrix`` record; callers use ``read_vendored_commit()`` to
get the *actual* commit from the submodule checkout (or ``None`` when the
submodule is absent / uninitialised). In pip-installed contexts where no
``.git`` directory exists, ``read_vendored_commit()`` returns ``None`` and
callers should fall back to ``VersionMatrix.pinned_comfyui_commit``.
"""
from __future__ import annotations

import json
from importlib import metadata as importlib_metadata
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vibecomfy.errors import DriftError

# Anchor the vendored-checkout lookup to the repo root (the package's parent),
# NOT the process CWD. ``vibecomfy/comfy_backend.py`` lives one level below the
# repo root, so ``parent.parent`` is the checkout that holds ``vendor/ComfyUI``.
# A CWD-relative path silently failed whenever a caller (e.g. the ``port export``
# CLI subprocess) ran from a tmp dir, which tripped the refuse.py hard import
# check. We keep the CWD-relative path as a fallback for unusual layouts.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_VENDOR_COMFY_CANDIDATES = (
    _REPO_ROOT / "vendor" / "ComfyUI",
    Path("vendor") / "ComfyUI",
)

# Memoized result of ensure_nodes(); ``None`` means "not yet computed".
_ENSURE_CACHE: bool | None = None

# Memoized result of load_version_matrix(); ``None`` means "not yet computed".
_VERSION_MATRIX_CACHE: VersionMatrix | None | _MissingSentinel = None


class _MissingSentinel:
    """Singleton sentinel for 'tried to load and it was missing'."""


_MISSING = _MissingSentinel()


# ---------------------------------------------------------------------------
# Version matrix data contract
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VersionMatrix:
    """Checked-in version pin for the vendored ComfyUI oracle.

    Loaded from the root ``version_matrix.json`` at most once per process.
    All fields are required; missing / malformed JSON raises immediately
    so drift is loud, not silent.
    """

    schema_version: str
    supported_comfyui_version: str
    pinned_comfyui_commit: str
    vendor_path: str
    object_info_fingerprint: dict[str, Any] | None = None


@dataclass(frozen=True)
class ComfyCompatibility:
    """Coarse S1 compatibility verdict for the live ComfyUI converter path."""

    ok: bool
    reason_code: str
    expected: dict[str, str | None]
    actual: dict[str, str | None]
    safe_families: list[str] = field(default_factory=list)


class ComfyCompatibilityError(DriftError):
    """Raised when live ComfyUI is incompatible with the checked-in oracle pin."""

    def __init__(self, compatibility: ComfyCompatibility):
        self.compatibility = compatibility
        super().__init__(
            (
                f"{compatibility.reason_code}: expected commit="
                f"{compatibility.expected.get('commit')!r}, version="
                f"{compatibility.expected.get('version')!r}; actual commit="
                f"{compatibility.actual.get('commit')!r}, version="
                f"{compatibility.actual.get('version')!r}"
            ),
            next_action=(
                "Use the pinned vendor/ComfyUI checkout or a matching installed "
                "ComfyUI build before running strict converter-backed paths."
            ),
        )


# ---------------------------------------------------------------------------
# Matrix loading
# ---------------------------------------------------------------------------


def _find_version_matrix_path() -> Path:
    """Locate ``version_matrix.json`` relative to the repo root.

    Returns the absolute path.  Does **not** check existence — callers
    decide how to handle a missing file.
    """
    return _REPO_ROOT / "version_matrix.json"


def load_version_matrix() -> VersionMatrix:
    """Load and validate the root ``version_matrix.json``.

    Returns a :class:`VersionMatrix` on success.  Raises typed errors for
    every failure mode so callers never receive a silently-incomplete record:

    * ``FileNotFoundError`` — the matrix file does not exist.
    * ``json.JSONDecodeError`` — the file is not valid JSON.
    * ``ValueError`` — a required key is missing or has the wrong type.
    * ``TypeError`` — a field has an unexpected type.

    The result is memoized: repeated calls return the same instance.
    """
    global _VERSION_MATRIX_CACHE
    if _VERSION_MATRIX_CACHE is not None:
        if _VERSION_MATRIX_CACHE is _MISSING:
            raise FileNotFoundError("version_matrix.json not found (cached)")
        return _VERSION_MATRIX_CACHE

    path = _find_version_matrix_path()
    if not path.is_file():
        _VERSION_MATRIX_CACHE = _MISSING
        raise FileNotFoundError(f"version_matrix.json not found at {path}")

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _VERSION_MATRIX_CACHE = _MISSING
        raise  # re-raise with original location info

    if not isinstance(raw, dict):
        _VERSION_MATRIX_CACHE = _MISSING
        raise TypeError(
            f"version_matrix.json must be a JSON object, got {type(raw).__name__}"
        )

    # --- required string fields ---
    missing: list[str] = []
    for key in (
        "schema_version",
        "supported_comfyui_version",
        "pinned_comfyui_commit",
        "vendor_path",
    ):
        if key not in raw:
            missing.append(key)
        elif not isinstance(raw[key], str):
            raise TypeError(
                f"version_matrix.json field '{key}' must be a string, "
                f"got {type(raw[key]).__name__}"
            )
    if missing:
        _VERSION_MATRIX_CACHE = _MISSING
        raise ValueError(
            f"version_matrix.json missing required field(s): {', '.join(missing)}"
        )

    # --- optional fingerprint ---
    fingerprint = raw.get("object_info_fingerprint")
    if fingerprint is not None and not isinstance(fingerprint, dict):
        raise TypeError(
            "version_matrix.json field 'object_info_fingerprint' must be "
            f"a JSON object or null, got {type(fingerprint).__name__}"
        )

    matrix = VersionMatrix(
        schema_version=raw["schema_version"],
        supported_comfyui_version=raw["supported_comfyui_version"],
        pinned_comfyui_commit=raw["pinned_comfyui_commit"],
        vendor_path=raw["vendor_path"],
        object_info_fingerprint=fingerprint,
    )
    _VERSION_MATRIX_CACHE = matrix
    return matrix


def reset_matrix_cache() -> None:
    """Reset the version-matrix memoization cache.  Test-only seam."""
    global _VERSION_MATRIX_CACHE
    _VERSION_MATRIX_CACHE = None


# ---------------------------------------------------------------------------
# Vendored ComfyUI commit / version reading
# ---------------------------------------------------------------------------


def _find_vendored_comfy_dir() -> Path | None:
    """Return the first *populated* vendored ComfyUI directory, or ``None``.

    An empty directory (submodule not initialised) is treated as absent
    so ``read_vendored_commit()`` returns ``None`` instead of escaping
    into a parent repo.
    """
    for candidate in _VENDOR_COMFY_CANDIDATES:
        resolved = candidate.resolve()
        if not resolved.is_dir():
            continue
        # Must contain at least one entry beyond '.' and '..'
        try:
            next(resolved.iterdir())
        except StopIteration:
            continue  # empty directory — submodule not initialised
        return resolved
    return None


def read_vendored_commit() -> str | None:
    """Read the *actual* commit SHA of the vendored ComfyUI submodule.

    Uses ``git rev-parse HEAD`` inside the checkout so it reflects the
    on-disk state.  Returns ``None`` when:

    * The ``vendor/ComfyUI`` directory does not exist (submodule not
      initialised).
    * The directory exists but is not a git repository (e.g. pip-installed
      package with only the matrix file).
    * ``git`` is not available on ``PATH``.

    Callers should fall back to
    :attr:`VersionMatrix.pinned_comfyui_commit` when this returns ``None``.
    """
    vendor_dir = _find_vendored_comfy_dir()
    if vendor_dir is None:
        return None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(vendor_dir),
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def read_live_comfy_version() -> str | None:
    """Best-effort version label for an installed/importable ComfyUI build."""
    for dist_name in ("comfyui", "ComfyUI"):
        try:
            version = importlib_metadata.version(dist_name)
        except importlib_metadata.PackageNotFoundError:
            continue
        if version:
            return str(version)

    for module_name in ("comfy", "comfy.version"):
        try:
            module = __import__(module_name, fromlist=["__name__"])
        except Exception:
            continue
        for attr in ("__version__", "VERSION", "version"):
            value = getattr(module, attr, None)
            if isinstance(value, str) and value:
                return str(value)
    return None


def check_comfy_compatibility() -> ComfyCompatibility:
    """Compare the active ComfyUI checkout/build against ``version_matrix.json``."""
    actual_commit = read_vendored_commit()
    actual_version = read_live_comfy_version()
    actual = {
        "commit": actual_commit,
        "version": actual_version,
    }
    try:
        matrix = load_version_matrix()
    except FileNotFoundError:
        return ComfyCompatibility(
            ok=False,
            reason_code="comfyui_version_matrix_missing",
            expected={"commit": None, "version": None},
            actual=actual,
            safe_families=[],
        )
    except (json.JSONDecodeError, TypeError, ValueError):
        return ComfyCompatibility(
            ok=False,
            reason_code="comfyui_version_matrix_invalid",
            expected={"commit": None, "version": None},
            actual=actual,
            safe_families=[],
        )

    expected = {
        "commit": matrix.pinned_comfyui_commit,
        "version": matrix.supported_comfyui_version,
    }
    if actual_commit is not None:
        return ComfyCompatibility(
            ok=actual_commit == matrix.pinned_comfyui_commit,
            reason_code="ok" if actual_commit == matrix.pinned_comfyui_commit else "comfyui_version_skew",
            expected=expected,
            actual=actual,
            safe_families=[],
        )
    if actual_version is not None:
        return ComfyCompatibility(
            ok=actual_version == matrix.supported_comfyui_version,
            reason_code="ok" if actual_version == matrix.supported_comfyui_version else "comfyui_version_skew",
            expected=expected,
            actual=actual,
            safe_families=[],
        )
    return ComfyCompatibility(
        ok=False,
        reason_code="comfyui_version_unknown",
        expected=expected,
        actual=actual,
        safe_families=[],
    )


def require_comfy_compatibility(
    compatibility: ComfyCompatibility | None = None,
) -> ComfyCompatibility:
    """Raise a typed error when strict live-ComfyUI execution is not compatible."""
    compatibility = compatibility or check_comfy_compatibility()
    if compatibility.ok:
        return compatibility
    raise ComfyCompatibilityError(compatibility)


# ---------------------------------------------------------------------------
# Backend adoption (existing API)
# ---------------------------------------------------------------------------


def _vendor_on_path() -> None:
    """Best-effort: prepend the vendored ComfyUI checkout to ``sys.path``.

    No-op when the submodule directory is absent (uninitialized submodule), so
    the subsequent import simply fails and the caller falls back.
    """
    vendor_dir = _find_vendored_comfy_dir()
    if vendor_dir is None:
        return
    resolved = str(vendor_dir)
    if resolved not in sys.path:
        sys.path.insert(0, resolved)


def ensure_nodes() -> bool:
    """Idempotently attempt to make the ComfyUI node catalog importable.

    Returns ``True`` when the comfy backend imported successfully, ``False``
    otherwise. Memoized: the import is attempted at most once per process, so
    repeated calls are cheap. Never raises — an absent ``[comfy]`` extra or an
    uninitialized ``vendor/ComfyUI`` submodule yields ``False`` and the caller
    proceeds on the pure-Python path.
    """
    global _ENSURE_CACHE
    if _ENSURE_CACHE is not None:
        return _ENSURE_CACHE
    try:
        _vendor_on_path()
        import comfy.component_model.workflow_convert  # noqa: F401
    except Exception:
        _ENSURE_CACHE = False
    else:
        _ENSURE_CACHE = True
    return _ENSURE_CACHE


def reset_cache() -> None:
    """Reset the memoization cache. Test-only seam."""
    global _ENSURE_CACHE
    _ENSURE_CACHE = None


__all__ = [
    "check_comfy_compatibility",
    "ComfyCompatibility",
    "ComfyCompatibilityError",
    "ensure_nodes",
    "load_version_matrix",
    "read_live_comfy_version",
    "read_vendored_commit",
    "require_comfy_compatibility",
    "reset_cache",
    "reset_matrix_cache",
    "VersionMatrix",
]
