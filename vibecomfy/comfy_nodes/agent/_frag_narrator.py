"""
Narrative context, deterministic fallback, and LLM narrator (T-039 extraction of the edit_narrator fragment).

Extracted from the edit.py exec-assembled fragments (T-039, ORACLE-6).
The fragment SOURCE string stays in edit.py until T-041 removes the machinery;
this module is the live implementation. Function bodies resolve their free
names from the assembled edit-module namespace at call time (marked with a
T-039 late import comment) so monkeypatches on edit.* stay visible exactly as
under the old exec assembly; guarded imports stay function-local.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any, Mapping


# ── Narrator defaults (SD3) ───────────────────────────────────────────────
_NARRATOR_DEFAULT_ROUTE = "openrouter"
_NARRATOR_DEFAULT_MODEL = "openrouter:deepseek/deepseek-v4-flash"


@dataclass
class NarrativeContext:
    """Compact summary of turn state used by the narrator to validate messages.

    Wraps the dict payload from ``_narrative_context_payload`` with typed
    accessors so callers do not need to reach into raw dict keys.
    """

    payload: dict[str, Any]

    @property
    def task(self) -> str:
        return str(self.payload.get("task") or "")

    @property
    def route(self) -> str:
        return str(self.payload.get("route") or "")

    @property
    def internal_kind(self) -> str:
        outcome = self.payload.get("outcome")
        if isinstance(outcome, Mapping):
            return str(outcome.get("internal_kind") or "")
        return ""

    @property
    def public_kind(self) -> str:
        outcome = self.payload.get("outcome")
        if isinstance(outcome, Mapping):
            return str(outcome.get("public_kind") or "")
        return ""

    @property
    def clarification_question(self) -> str:
        outcome = self.payload.get("outcome")
        if isinstance(outcome, Mapping):
            return str(outcome.get("clarification_question") or "").strip()
        return ""

    @property
    def graph_changed(self) -> bool:
        change = self.payload.get("change")
        if isinstance(change, Mapping):
            return bool(change.get("graph_changed"))
        return False

    @property
    def landed_operation_count(self) -> int:
        change = self.payload.get("change")
        if isinstance(change, Mapping):
            return int(change.get("landed_operation_count") or 0)
        return 0

    @property
    def validation_passed(self) -> bool:
        validation = self.payload.get("validation")
        if isinstance(validation, Mapping):
            return bool(validation.get("passed"))
        return False

    @property
    def failure_kind(self) -> str:
        failure = self.payload.get("failure")
        if isinstance(failure, Mapping):
            return str(failure.get("kind") or "")
        return ""

    @property
    def failure_message(self) -> str:
        failure = self.payload.get("failure")
        if isinstance(failure, Mapping):
            return str(failure.get("message") or "")
        return ""

    @property
    def apply_eligibility_applyable(self) -> bool:
        eligibility = self.payload.get("apply_eligibility")
        if isinstance(eligibility, Mapping):
            return bool(eligibility.get("applyable"))
        return False

    def to_dict(self) -> dict[str, Any]:
        return dict(self.payload)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "NarrativeContext":
        return cls(payload=dict(payload))


# ── Fast-path predicate (SD1) ─────────────────────────────────────────────

def _narrator_fast_path_applies(narrative_context: NarrativeContext) -> bool:
    """Return True when the turn qualifies for the deterministic fast-path.

    SD1: Clean simple successes (outcome=edit, graph_changed=true,
    landed_ops>0, validation_passed, no warnings/blocks) skip the LLM
    narrator entirely and use a deterministic template.
    """
    if narrative_context.internal_kind != "edit":
        return False
    if not narrative_context.graph_changed:
        return False
    if narrative_context.landed_operation_count <= 0:
        return False
    if not narrative_context.validation_passed:
        return False
    # Warnings or blocks appear as failure_kind or validation issues.
    if narrative_context.failure_kind:
        return False
    return True


# ── Env-driven route/model read (SD3) ─────────────────────────────────────

def _narrator_route() -> str | None:
    """Return the narrator route, respecting VIBECOMFY_NARRATOR_ROUTE env var.

    Returns None when the env var is unset so callers can distinguish
    between explicit configuration and the default.
    """
    return os.getenv("VIBECOMFY_NARRATOR_ROUTE") or None


def _narrator_model() -> str | None:
    """Return the narrator model, respecting VIBECOMFY_NARRATOR_MODEL env var.

    Returns None when the env var is unset so callers can distinguish
    between explicit configuration and the default.
    """
    return os.getenv("VIBECOMFY_NARRATOR_MODEL") or None


# ── Assembly helper ───────────────────────────────────────────────────────

def _assemble_narrative_context(
    state: AgentEditState,
    context: TurnContext,
    *,
    outcome: TurnOutcome | None = None,
    failure: FailureEnvelope | None = None,
    public_outcome: str | None = None,
    apply_eligibility: ApplyEligibility | None = None,
    change_details: Mapping[str, Any] | None = None,
) -> NarrativeContext:
    from vibecomfy.comfy_nodes.agent.edit import (NarrativeContext, _narrative_context_payload)  # T-039 late import: host namespace lookup; resolved at call time
    """Build a ``NarrativeContext`` from the current turn state.

    Delegates to the existing ``_narrative_context_payload`` helper in
    ``edit_humanize`` so the compact summary stays consistent.
    """
    payload = _narrative_context_payload(
        state,
        context,
        outcome=outcome,
        failure=failure,
        public_outcome=public_outcome,
        apply_eligibility=apply_eligibility,
        change_details=change_details,
    )
    return NarrativeContext.from_dict(payload)


# ── Guard helper ──────────────────────────────────────────────────────────

def _guard_narrative_message(
    message: str,
    narrative_context: NarrativeContext,
) -> dict[str, Any]:
    from vibecomfy.comfy_nodes.agent.edit import (_validate_narrative_message)  # T-039 late import: host namespace lookup; resolved at call time
    """Run deterministic guard checks on *message* against *narrative_context*.

    Returns the same shape as ``_validate_narrative_message``:
    ``{"ok": bool, "message": str, "issues": list[str]}``.
    """
    return _validate_narrative_message(message, narrative_context=narrative_context.payload)


# ── Deterministic fallback ────────────────────────────────────────────────

def _deterministic_narrative_fallback(
    state: AgentEditState,
    *,
    outcome: TurnOutcome | None = None,
    failure: FailureEnvelope | None = None,
    narrative_context: NarrativeContext | None = None,
    fallback_reason: str | None = None,
) -> str:
    from vibecomfy.comfy_nodes.agent.edit import (_fallback_narrative_message)  # T-039 late import: host namespace lookup; resolved at call time
    """Produce a deterministic (non-LLM) fallback message.

    Delegates to ``_fallback_narrative_message`` in ``edit_humanize``
    which uses the existing humanizing helpers to build a safe message.
    """
    ctx_payload = narrative_context.payload if narrative_context is not None else None
    return _fallback_narrative_message(
        state,
        outcome=outcome,
        failure=failure,
        narrative_context=ctx_payload,
        fallback_reason=fallback_reason,
    )


# ── Best-effort artifact writer ───────────────────────────────────────────

def _write_narrative_artifacts(
    state: AgentEditState,
    narrative_context: NarrativeContext,
    validation: dict[str, Any],
    *,
    request_messages: list[dict[str, str]] | None = None,
    llm_response: dict[str, Any] | None = None,
) -> None:
    from vibecomfy.comfy_nodes.agent.edit import (LOGGER)  # T-039 late import: host namespace lookup; resolved at call time
    """Best-effort write of narrative artifacts to the turn directory.

    Always writes:
    - ``narrative_context.json``
    - ``narrative_validation.json``

    Writes when available:
    - ``narrator_request.json`` (when *request_messages* is not None)
    - ``narrator_response.json`` (when *llm_response* is not None)

    Failures are logged and swallowed; artifacts are best-effort only.
    """
    turn_dir = state.turn_dir
    try:
        turn_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

    def _safe_write(rel_path: str, data: Any) -> None:
        try:
            target = turn_dir / rel_path
            target.write_text(
                json.dumps(data, indent=2, sort_keys=True, default=str) + "\n",
                encoding="utf-8",
            )
        except (OSError, ValueError, TypeError) as exc:
            LOGGER.warning(
                "Narrative artifact %s write failed for turn %s (best-effort): %s",
                rel_path,
                getattr(state, "turn_dir", None),
                exc,
            )

    _safe_write("narrative_context.json", narrative_context.payload)
    _safe_write("narrative_validation.json", validation)

    if request_messages is not None:
        _safe_write("narrator_request.json", request_messages)

    if llm_response is not None:
        _safe_write("narrator_response.json", llm_response)


# ── Prompt construction helpers ───────────────────────────────────────────

_NARRATOR_SYSTEM_PROMPT = (
    "You are a concise, honest narrative synthesizer for a visual programming "
    "agent. The agent just completed a graph-editing turn. Your job is to "
    "produce a single user-facing sentence that accurately describes what "
    "happened.\n\n"
    "Rules:\n"
    "- Respond with exactly one JSON object: {\"message\": \"...\"}\n"
    "- The message must be one natural-language sentence ending in punctuation.\n"
    "- Never mention internal agent machinery (gates, validation, scoring, "
    "batch REPL, field changes). Use the user-facing narrative context only.\n"
    "- If the outcome is a clarification question, the message should ask it "
    "politely.\n"
    "- If the outcome is a failure, be honest but helpful about what went wrong.\n"
    "- If edits landed, describe what changed in plain language.\n"
    "- If nothing changed, say so honestly without inventing edits.\n"
    "- Never include markdown, code fences, or structured data in the message.\n"
    "- Keep the message under 300 characters."
)


def _build_narrator_messages(
    narrative_context: NarrativeContext,
    *,
    raw_executor_message: str = "",
    fallback_message: str = "",
) -> list[dict[str, str]]:
    from vibecomfy.comfy_nodes.agent.edit import (_NARRATOR_SYSTEM_PROMPT)  # T-039 late import: host namespace lookup; resolved at call time
    """Build the message list for the LLM narrator call."""
    context_json = json.dumps(narrative_context.payload, indent=2, sort_keys=True)
    user_content_parts: list[str] = [
        "Turn narrative context (JSON):",
        context_json,
    ]
    if raw_executor_message:
        user_content_parts.append(f"\nRaw executor message: {raw_executor_message[:240]}")
    if fallback_message:
        user_content_parts.append(f"\nFallback message (use as reference): {fallback_message}")
    user_content_parts.append("\nProduce the user-facing message as a JSON object.")
    return [
        {"role": "system", "content": _NARRATOR_SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(user_content_parts)},
    ]


# ── Provider-backed LLM call ──────────────────────────────────────────────

def _call_narrator_llm(
    narrative_context: NarrativeContext,
    messages: list[dict[str, str]],
    *,
    route: str,
    model: str,
) -> tuple[str, dict[str, Any]]:
    from vibecomfy.comfy_nodes.agent.edit import (MalformedModelJSON, MissingRequiredField, ProviderError, _narrator_message_from_response, run_model_turn)  # T-039 late import: host namespace lookup; resolved at call time
    """Call the LLM narrator through the provider and extract the message.

    Returns ``(message, raw_response)``.  The *message* is extracted from
    the JSON response; *raw_response* is the full dict for artifact recording.

    Raises :class:`ProviderError`, :class:`AuthError`, :class:`MalformedModelJSON`,
    or :class:`TimeoutError` on failure — callers must catch these.
    """
    try:
        raw = run_model_turn(
            task=narrative_context.task or "narrate turn outcome",
            messages=messages,
            route=route,
            model=model,
            response_contract="json",
        )
    except TimeoutError:
        raise
    except ImportError:
        raise ProviderError("Narrator runtime unavailable (import error).")
    except (ProviderError, MalformedModelJSON, MissingRequiredField):
        raise
    except Exception as exc:
        raise ProviderError(f"Narrator LLM call failed: {exc}") from exc

    if not isinstance(raw, dict):
        raise MalformedModelJSON(
            "Narrator response was not a JSON object.",
            raw_response=str(raw)[:500],
            parse_reason="non_dict_response",
        )

    # Use the canonical extraction helper from edit_humanize which handles
    # the 'json' wrapper key that run_model_turn returns.
    message_raw = _narrator_message_from_response(raw)

    return message_raw, raw


# ── Main entrypoint with fast-path + LLM + guard + fallback ───────────────

def _narrate_final_message(
    state: AgentEditState,
    context: TurnContext,
    *,
    outcome: TurnOutcome | None = None,
    failure: FailureEnvelope | None = None,
    public_outcome: str | None = None,
    apply_eligibility: ApplyEligibility | None = None,
) -> str:
    from vibecomfy.comfy_nodes.agent.edit import (LOGGER, MalformedModelJSON, ProviderError, _NARRATOR_DEFAULT_MODEL, _NARRATOR_DEFAULT_ROUTE, _assemble_narrative_context, _build_narrator_messages, _call_narrator_llm, _deterministic_narrative_fallback, _guard_narrative_message, _narrator_fast_path_applies, _narrator_model, _narrator_route, _write_narrative_artifacts)  # T-039 late import: host namespace lookup; resolved at call time
    """Produce the final user-facing message for a completed agent-edit turn.

    Design decisions SD1–SD3 (see plan_v1.meta.json):
      - SD1: clean simple successes use deterministic fast-path and skip LLM.
      - SD2: LLM narrator is invoked for success-with-warnings, clarify, noop,
        blocked, budget, and failure outcomes.
      - SD3: default route/model is openrouter/deepseek-v4-flash, overridable
        via VIBECOMFY_NARRATOR_ROUTE and VIBECOMFY_NARRATOR_MODEL env vars.

    The fast-path writes compact narrative_context.json and
    narrative_validation.json artifacts.  The LLM path additionally writes
    narrator_request.json and narrator_response.json.  All artifact writes
    are best-effort (failures logged and swallowed).
    """
    try:
        # ── Assemble context ──────────────────────────────────────────
        narrative_context = _assemble_narrative_context(
            state,
            context,
            outcome=outcome,
            failure=failure,
            public_outcome=public_outcome,
            apply_eligibility=apply_eligibility,
        )

        # ── SD1: Fast-path for clean simple successes ─────────────────
        if _narrator_fast_path_applies(narrative_context):
            message = _deterministic_narrative_fallback(
                state,
                outcome=outcome,
                failure=failure,
                narrative_context=narrative_context,
            )
            validation = _guard_narrative_message(message, narrative_context)
            _write_narrative_artifacts(state, narrative_context, validation)

            if validation.get("ok"):
                return message

            # Guard rejected fast-path message (should be extremely rare).
            # Fall through to raw fallback without context.
            LOGGER.warning(
                "Narrator fast-path message failed guard: %s",
                validation.get("issues", []),
            )
            raw_fallback = _deterministic_narrative_fallback(
                state,
                outcome=outcome,
                failure=failure,
                narrative_context=None,
                fallback_reason="guard_rejected_fast_path",
            )
            # Write a secondary validation artifact for the raw fallback.
            fallback_validation = _guard_narrative_message(
                raw_fallback,
                narrative_context,
            )
            _write_narrative_artifacts(
                state,
                narrative_context,
                fallback_validation,
            )
            return raw_fallback

        # ── SD2/SD3: LLM narrator path ───────────────────────────────

        # Resolve route/model from env vars with defaults.
        route = _narrator_route() or _NARRATOR_DEFAULT_ROUTE
        model = _narrator_model() or _NARRATOR_DEFAULT_MODEL

        # Pre-compute the deterministic fallback in case the LLM path fails.
        fallback_message = _deterministic_narrative_fallback(
            state,
            outcome=outcome,
            failure=failure,
            narrative_context=narrative_context,
        )

        llm_request: list[dict[str, str]] | None = None
        llm_response: dict[str, Any] | None = None
        llm_message: str | None = None
        fallback_reason: str | None = None

        try:
            raw_executor_message = " ".join((state.raw_executor_message or "").split())
            llm_request = _build_narrator_messages(
                narrative_context,
                raw_executor_message=raw_executor_message,
                fallback_message=fallback_message,
            )
            llm_message, llm_response = _call_narrator_llm(
                narrative_context,
                llm_request,
                route=route,
                model=model,
            )
        except ProviderError as exc:
            LOGGER.warning("Narrator provider error (%s), falling back: %s", type(exc).__name__, exc)
            fallback_reason = "provider_failure"
        except MalformedModelJSON as exc:
            LOGGER.warning("Narrator malformed response, falling back: %s", exc)
            fallback_reason = "malformed_response"
        except TimeoutError:
            LOGGER.warning("Narrator LLM call timed out, falling back.")
            fallback_reason = "provider_failure"
        except Exception as exc:
            LOGGER.warning(
                "Narrator LLM unexpected error (%s), falling back: %s",
                type(exc).__name__,
                exc,
            )
            fallback_reason = "provider_failure"

        # Guard LLM output when available.
        validation: dict[str, Any] = {"ok": False, "message": "", "issues": ["llm_not_called"]}
        if llm_message is not None and fallback_reason is None:
            validation = _guard_narrative_message(llm_message, narrative_context)
            if validation.get("ok"):
                _write_narrative_artifacts(
                    state,
                    narrative_context,
                    validation,
                    request_messages=llm_request,
                    llm_response=llm_response,
                )
                return llm_message

            # LLM message failed guard checks — fall back.
            LOGGER.warning(
                "Narrator LLM message failed guard checks: %s",
                validation.get("issues", []),
            )
            fallback_reason = "refused_narrative"
        elif llm_message is not None:
            # fallback_reason is set from an exception above.
            validation = _guard_narrative_message(llm_message, narrative_context)

        # ── Fallback: use deterministic message ───────────────────────
        fallback_validation = _guard_narrative_message(fallback_message, narrative_context)

        _write_narrative_artifacts(
            state,
            narrative_context,
            fallback_validation,
            request_messages=llm_request,
            llm_response=llm_response,
        )

        if fallback_validation.get("ok"):
            return fallback_message

        # Guard rejected even the fallback — return raw fallback without context.
        LOGGER.warning(
            "Narrator fallback message also failed guard: %s",
            fallback_validation.get("issues", []),
        )
        raw_fallback = _deterministic_narrative_fallback(
            state,
            outcome=outcome,
            failure=failure,
            narrative_context=None,
            fallback_reason="guard_rejected_fallback",
        )
        return raw_fallback

    except Exception as exc:
        LOGGER.warning(
            "Narrator unrecoverable error (%s), returning raw fallback: %s",
            type(exc).__name__,
            exc,
        )
        return _deterministic_narrative_fallback(
            state,
            outcome=outcome,
            failure=failure,
            narrative_context=None,
            fallback_reason="narrator_unrecoverable_error",
        )


__all__ = (
    "NarrativeContext",
    "_NARRATOR_DEFAULT_MODEL",
    "_NARRATOR_DEFAULT_ROUTE",
    "_NARRATOR_SYSTEM_PROMPT",
    "_assemble_narrative_context",
    "_build_narrator_messages",
    "_call_narrator_llm",
    "_deterministic_narrative_fallback",
    "_guard_narrative_message",
    "_narrate_final_message",
    "_narrator_fast_path_applies",
    "_narrator_model",
    "_narrator_route",
    "_write_narrative_artifacts",
)
