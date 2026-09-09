"""Compatibility helper for importing ComfyUI's PromptServer.

VibeComfy historically assumed a checkout-style ComfyUI layout where the
running interpreter can do ``from server import PromptServer``. The
pip-installable ComfyUI fork keeps the server class at
``comfy.cmd.server.PromptServer`` and installs a ``sys.modules['server']`` shim
via ``comfy_compatibility.vanilla.prepare_vanilla_environment()``.

This module provides a single import helper that works for both layouts so
VibeComfy custom nodes can register HTTP routes in either environment.
"""

from __future__ import annotations

import sys


_OFFICIAL_PROMPT_SERVER_STUB_TYPE = None


def import_prompt_server():
    """Return ComfyUI's ``PromptServer`` class.

    Tries the legacy checkout-style import first, then activates the
    pip-install compatibility shim if needed, then falls back to importing
    directly from ``comfy.cmd.server``.

    Raises
    ------
    ImportError
        If PromptServer cannot be resolved in any layout.
    """
    try:
        from server import PromptServer

        return PromptServer
    except ImportError:
        pass

    try:
        from comfy_compatibility.vanilla import prepare_vanilla_environment

        prepare_vanilla_environment()
        from server import PromptServer

        return PromptServer
    except Exception:
        pass

    # Final fallback for pip-installed ComfyUI when the shim is not present.
    from comfy.cmd.server import PromptServer

    return PromptServer


def is_official_import_only_stub(instance: object) -> bool:
    """Identify only pip Comfy's private import-time PromptServer stub.

    Missing middleware is not sufficient evidence on its own: a malformed
    live server must continue through the strict security installer and fail.
    """
    # vanilla_node_importing is loaded as part of Comfy's node import pass.  Do
    # not import it here: importing that module a second time can re-register
    # Comfy torch operators.  Looking up the already-loaded module still keeps
    # this an exact-type check and avoids class-name or duck-typing bypasses.
    global _OFFICIAL_PROMPT_SERVER_STUB_TYPE
    module = sys.modules.get("comfy.nodes.vanilla_node_importing")
    discovered_type = getattr(module, "_PromptServerStub", None)
    if discovered_type is not None:
        _OFFICIAL_PROMPT_SERVER_STUB_TYPE = discovered_type
    stub_type = _OFFICIAL_PROMPT_SERVER_STUB_TYPE
    if stub_type is None:
        return False
    if type(instance) is not stub_type:
        return False
    app = getattr(instance, "app", None)
    return app is not None and (
        getattr(app, "middlewares", None) is None
        or getattr(app, "on_startup", None) is None
    )
