from __future__ import annotations

import contextvars
from typing import TYPE_CHECKING

from vibecomfy.errors import ContextVarBindingError

if TYPE_CHECKING:
    from vibecomfy.workflow import VibeWorkflow


_CURRENT_WORKFLOW: contextvars.ContextVar[VibeWorkflow | None] = contextvars.ContextVar(
    "vibecomfy_current_workflow",
    default=None,
)


def bind_workflow(wf: VibeWorkflow) -> contextvars.Token[VibeWorkflow | None]:
    """Bind ``wf`` as the active workflow for context-bound node wrappers."""
    if _CURRENT_WORKFLOW.get() is not None:
        raise ContextVarBindingError(
            "Nested workflow contexts not supported. The outer `with new_workflow(...)` "
            "block is still active.",
            next_action="vibecomfy doctor",
        )
    return _CURRENT_WORKFLOW.set(wf)


def reset_workflow(token: contextvars.Token[VibeWorkflow | None]) -> None:
    """Reset the active workflow binding created by ``bind_workflow``."""
    _CURRENT_WORKFLOW.reset(token)


def _current_workflow_or_raise() -> VibeWorkflow:
    wf = _CURRENT_WORKFLOW.get()
    if wf is None:
        raise ContextVarBindingError(
            "No active workflow. Start your build with "
            "`wf = new_workflow(READY_METADATA, source_path=__file__)`.",
            next_action="vibecomfy doctor",
        )
    return wf


def active_workflow() -> VibeWorkflow | None:
    """Return the currently bound workflow, if any."""
    return _CURRENT_WORKFLOW.get()


def unbind_workflow(wf: VibeWorkflow | None) -> None:
    """Idempotent, identity-checked release of the active workflow binding.

    Unlike :func:`reset_workflow`, this NEVER calls ``Token.reset()``.
    ``contextvars.Token`` is single-use and LIFO, so resetting one token from
    the several unbind sites that now share ownership (``_finalize_impl``,
    ``VibeWorkflow.__exit__``, and the loader ``finally`` guards) would raise
    ``RuntimeError``. Instead this clears the ContextVar to ``None`` only when
    *wf* is the currently bound workflow, then clears the stored token so a
    later :func:`bind_workflow` starts clean. Safe to call repeatedly and from
    multiple sites for the same workflow; a ``None`` argument is a no-op.
    """
    if wf is None:
        return
    if active_workflow() is wf:
        _CURRENT_WORKFLOW.set(None)
    try:
        wf._workflow_context_token = None
    except AttributeError:
        pass
