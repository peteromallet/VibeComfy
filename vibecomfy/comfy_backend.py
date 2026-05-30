"""Optional ComfyUI backend adoption hook (M2 Step 7, SD2).

This module is an OPTIONAL optimization, never a hard dependency. M2's identity
derivation is pure-Python (see ``vibecomfy.porting.scope.sg_key``); nothing in
the M2 feature set requires a real ComfyUI node catalog. ``ensure_nodes()`` lets
a caller *adopt* the real catalog when it happens to be available — either via
the ``[comfy]`` optional-dependency extra or the vendored ``vendor/ComfyUI``
submodule — and otherwise returns ``False`` so callers fall back to the
pure-Python path without error.

The import is guarded by ``try/except`` and memoized so it is attempted at most
once per process. When the extra is not installed AND the submodule is
uninitialized, ``ensure_nodes()`` returns ``False`` and never raises.
"""
from __future__ import annotations

import sys
from pathlib import Path

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


def _vendor_on_path() -> None:
    """Best-effort: prepend the vendored ComfyUI checkout to ``sys.path``.

    No-op when the submodule directory is absent (uninitialized submodule), so
    the subsequent import simply fails and the caller falls back.
    """
    for candidate in _VENDOR_COMFY_CANDIDATES:
        if not candidate.is_dir():
            continue
        resolved = str(candidate.resolve())
        if resolved not in sys.path:
            sys.path.insert(0, resolved)
        return


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


__all__ = ["ensure_nodes", "reset_cache"]
