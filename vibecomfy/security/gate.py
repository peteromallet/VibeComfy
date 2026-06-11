"""S4 capability fence — provenance request scope and confirmation gate.

This module provides two complementary surfaces:

1. ``requesting_provenance`` / ``untrusted_scope`` — a ContextVar that ambient
   callers (ingest, install, loader, agent surface) set so the gate and
   metadata-tagging sites can read it without threading an explicit kwarg
   through every public surface. Defaults to ``"agent_authored"`` because
   almost every authoring entry point is the agent editing the IR; only ingest
   of external workflow JSON enters ``untrusted_scope()`` to flip the default
   to ``"untrusted_source"``.

2. ``require_confirmation`` — the confused-deputy gate. Called by any
   IR-mutating surface that is about to install untrusted, side-effecting
   capability into the workflow. Returns the literal string ``"allow"`` on
   success, raises ``CapabilityFenceError`` (carrying ``.detail``) on refusal.
   ``agent_generated`` is allowed here for headless execution, but only the
   restricted generated-Python loader is allowed to mint that provenance.

The dependency direction stays one-way: ``security/`` never imports from
``ingest``/``workflow``/``porting``/``registry``; those packages import this
module.
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import IO, Any, Iterable, Iterator, Literal

from vibecomfy.security.provenance import Provenance

requesting_provenance: ContextVar[Provenance] = ContextVar(
    "requesting_provenance", default="agent_authored"
)


@contextmanager
def untrusted_scope() -> Iterator[None]:
    """Set ``requesting_provenance`` to ``"untrusted_source"`` for the block.

    Restores the prior value via the ContextVar token on exit, even if the
    body raises. Safe to nest.
    """
    token = requesting_provenance.set("untrusted_source")
    try:
        yield
    finally:
        requesting_provenance.reset(token)


# ---------------------------------------------------------------------------
# Capability fence
# ---------------------------------------------------------------------------


class CapabilityFenceError(Exception):
    """Raised by ``require_confirmation`` when the gate refuses the operation.

    ``.detail`` is a JSON-serializable dict describing the refusal (operation,
    class_type, provenance, capabilities, reason, details). The CLI ``main``
    surfaces this as a structured stderr payload and exits with code 42.
    """

    def __init__(self, detail: dict[str, Any]):
        self.detail = detail
        super().__init__(detail.get("reason", "capability fence refused operation"))


def _default_stream_for(attr: str) -> IO[Any]:
    return getattr(sys, attr)


@dataclass
class GateContext:
    """Per-process gate configuration.

    Stored in a ContextVar so nested calls inherit settings without threading
    explicit args. Audit accumulates every gate decision for later inspection
    (including ``--yes`` bypasses, which is the whole point of an audit log).
    """

    non_interactive: bool
    assume_yes: bool
    audit: list[dict[str, Any]] = field(default_factory=list)
    stdin: IO[Any] = field(default_factory=lambda: _default_stream_for("stdin"))
    stdout: IO[Any] = field(default_factory=lambda: _default_stream_for("stdout"))


def _safe_default_context() -> GateContext:
    try:
        non_interactive = not sys.stdin.isatty()
    except (AttributeError, ValueError, OSError):
        non_interactive = True
    return GateContext(
        non_interactive=non_interactive,
        assume_yes=False,
        audit=[],
    )


_gate_context_var: ContextVar[GateContext] = ContextVar(
    "_gate_context_var", default=_safe_default_context()
)


def current_gate_context() -> GateContext:
    """Return the active ``GateContext`` (falling back to the safe default)."""
    return _gate_context_var.get()


def set_gate_context(ctx: GateContext) -> Any:
    """Install ``ctx`` as the active gate context; returns the reset token."""
    return _gate_context_var.set(ctx)


def _record(
    ctx: GateContext,
    *,
    decision: str,
    operation: str,
    class_type: str,
    provenance: Provenance,
    capabilities: Iterable[str],
    details: dict[str, Any] | None,
    reason: str,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "decision": decision,
        "operation": operation,
        "class_type": class_type,
        "provenance": provenance,
        "capabilities": sorted({str(c) for c in capabilities}),
        "reason": reason,
        "details": dict(details or {}),
    }
    ctx.audit.append(entry)
    return entry


def require_confirmation(
    *,
    operation: str,
    class_type: str,
    provenance: Provenance,
    capabilities: Iterable[str],
    details: dict[str, Any] | None = None,
    ctx: GateContext | None = None,
) -> Literal["allow"]:
    """Gate a potentially-deputy operation.

    Allow rules (in order):
      - ``provenance`` ∈ {agent_authored, agent_generated, user_confirmed}
                                                                     → allow
      - effective capabilities ⊆ {passthrough}                          → allow
      - ``ctx.assume_yes``                                              → audit + allow
      - ``ctx.non_interactive`` or ``not stream.isatty()``              → raise
      - otherwise: render a structured y/n prompt; ``y``/``yes`` → allow,
        anything else → raise
    """
    ctx = ctx if ctx is not None else current_gate_context()
    caps = frozenset(str(c) for c in capabilities)
    details = dict(details or {})

    # Trusted or restricted-loader provenance. `agent_generated` must remain
    # mintable only by the restricted loader; the gate merely recognizes that
    # provenance once present so headless execution can proceed.
    if provenance in ("agent_authored", "agent_generated", "user_confirmed"):
        _record(
            ctx,
            decision="allow",
            operation=operation,
            class_type=class_type,
            provenance=provenance,
            capabilities=caps,
            details=details,
            reason="trusted_provenance",
        )
        return "allow"

    if caps and caps <= frozenset({"passthrough"}):
        _record(
            ctx,
            decision="allow",
            operation=operation,
            class_type=class_type,
            provenance=provenance,
            capabilities=caps,
            details=details,
            reason="passthrough_only",
        )
        return "allow"

    if ctx.assume_yes:
        _record(
            ctx,
            decision="allow",
            operation=operation,
            class_type=class_type,
            provenance=provenance,
            capabilities=caps,
            details=details,
            reason="assume_yes_bypass",
        )
        return "allow"

    is_tty = False
    if not ctx.non_interactive:
        try:
            is_tty = bool(ctx.stdin.isatty())
        except (AttributeError, ValueError, OSError):
            is_tty = False

    if ctx.non_interactive or not is_tty:
        detail = {
            "reason": "non_interactive_refusal",
            "operation": operation,
            "class_type": class_type,
            "provenance": provenance,
            "capabilities": sorted(caps),
            "details": details,
        }
        _record(
            ctx,
            decision="deny",
            operation=operation,
            class_type=class_type,
            provenance=provenance,
            capabilities=caps,
            details=details,
            reason="non_interactive_refusal",
        )
        raise CapabilityFenceError(detail)

    # Interactive y/n
    risky_lines = [f"  {k}: {v!r}" for k, v in sorted(details.items())]
    prompt_lines = [
        "vibecomfy capability fence — confirm operation:",
        f"  operation:  {operation}",
        f"  class_type: {class_type}",
        f"  provenance: {provenance}",
        f"  capabilities: {', '.join(sorted(caps)) or '(none)'}",
    ]
    if risky_lines:
        prompt_lines.append("  risky params:")
        prompt_lines.extend(risky_lines)
    prompt_lines.append("Allow? [y/N]: ")
    try:
        ctx.stdout.write("\n".join(prompt_lines))
        ctx.stdout.flush()
    except Exception:
        pass
    answer = ctx.stdin.readline().strip().lower()
    if answer in ("y", "yes"):
        _record(
            ctx,
            decision="allow",
            operation=operation,
            class_type=class_type,
            provenance=provenance,
            capabilities=caps,
            details=details,
            reason="interactive_confirm",
        )
        return "allow"

    detail = {
        "reason": "interactive_refusal",
        "operation": operation,
        "class_type": class_type,
        "provenance": provenance,
        "capabilities": sorted(caps),
        "details": details,
        "answer": answer,
    }
    _record(
        ctx,
        decision="deny",
        operation=operation,
        class_type=class_type,
        provenance=provenance,
        capabilities=caps,
        details=details,
        reason="interactive_refusal",
    )
    raise CapabilityFenceError(detail)


__all__ = [
    "CapabilityFenceError",
    "GateContext",
    "current_gate_context",
    "require_confirmation",
    "requesting_provenance",
    "set_gate_context",
    "untrusted_scope",
]
