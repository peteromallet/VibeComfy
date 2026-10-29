"""S4 Step 10 — provenance classifier for `exec_module` loader call sites.

Used by ``vibecomfy/scratchpad_loader.py`` and ``vibecomfy/registry/ready.py``
to decide, *before* ``spec.loader.exec_module(...)`` fires, whether the source
file lives under a trusted in-repo directory (``out/scratchpads/`` or the
built-in ``ready_templates/`` directory) or is an external, attacker-controlled
path.

Classification uses ``Path.resolve()`` + ``pathlib.Path.is_relative_to``
against the resolved trusted-directory paths. This defeats traversal
(``out/scratchpads/../../tmp/evil.py``) and symlink-escape attacks that a
prefix-string match would miss.
"""

from __future__ import annotations

from pathlib import Path

from vibecomfy.errors import CheckoutRequiredError
from vibecomfy.security.provenance import Provenance
from vibecomfy.utils import find_repo_root


def _trusted_roots() -> list[Path]:
    """Resolved trusted-directory roots for exec_module loaders.

    Trust checkout scratchpads and ready templates, or the installed package's
    ready templates when there is no checkout. Resolve roots before comparison
    to catch traversal and symlink escapes.
    """
    roots: list[Path] = []
    try:
        repo = find_repo_root()
    except CheckoutRequiredError:
        # A wheel ships templates inside the package; scratchpads remain
        # checkout-only. Never let a symlinked corpus root widen this trust.
        package = Path(__file__).resolve().parents[1]
        try:
            packaged = (package / "ready_templates").resolve()
            if packaged.is_relative_to(package) and packaged.is_dir():
                roots.append(packaged)
        except OSError:
            pass
        return roots

    for candidate in (repo / "out" / "scratchpads", repo / "ready_templates"):
        try:
            roots.append(candidate.resolve())
        except OSError:
            continue
    return roots


def _provenance_for_path(path: Path) -> Provenance:
    """Classify an exec_module source file path as trusted or untrusted.

    Returns ``"agent_authored"`` if ``path.resolve()`` is under either of the
    trusted roots, otherwise ``"untrusted_source"``. Never uses prefix-string
    matching.
    """
    try:
        resolved = Path(path).resolve()
    except OSError:
        return "untrusted_source"
    for root in _trusted_roots():
        try:
            if resolved.is_relative_to(root):
                return "agent_authored"
        except (ValueError, OSError):
            continue
    return "untrusted_source"


__all__ = ["_provenance_for_path"]
