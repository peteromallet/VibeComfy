# Generated from edit.py. Keep behavior changes in the installed source body.
# Contents: NarrativeContext, fact-grounded LLM narrator synthesis, deterministic
#   fallback generation, narrator route/model handling, and the always-ships
#   _narrate_final_message entrypoint with best-effort artifact persistence.

SOURCE = r'''
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


# ── Deterministic fallback ────────────────────────────────────────────────

def _deterministic_narrative_fallback(
    state: AgentEditState,
    *,
    outcome: TurnOutcome | None = None,
    failure: FailureEnvelope | None = None,
    narrative_context: NarrativeContext | None = None,
    fallback_reason: str | None = None,
) -> str:
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
    "- Keep the message under 300 characters.\n"
    "You MUST state what happened per these structured facts and describe "
    "exactly those facts:\n"
    "  - change.graph_unchanged: whether the graph changed (true = unchanged).\n"
    "  - outcome.kind: the public outcome kind (e.g. candidate, noop, clarify, failure).\n"
    "  - change.landed_operation_count: how many operations actually landed.\n"
    "  - validation.passed: whether post-edit validation passed.\n"
    "Never claim an edit you did not land: when graph_unchanged is true or "
    "landed_operation_count is 0, you MUST NOT say the graph was edited, "
    "applied, updated, connected, or changed. Never claim validation passed "
    "when validation.passed is false. The message must be consistent with "
    "every one of these fields."
)


def _build_narrator_messages(
    narrative_context: NarrativeContext,
    *,
    raw_executor_message: str = "",
    fallback_message: str = "",
) -> list[dict[str, str]]:
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


# ── Main entrypoint (LLM narrator is the sole path) ───────────────────────

def _narrate_final_message(
    state: AgentEditState,
    context: TurnContext,
    *,
    outcome: TurnOutcome | None = None,
    failure: FailureEnvelope | None = None,
    public_outcome: str | None = None,
    apply_eligibility: ApplyEligibility | None = None,
) -> str:
    """Produce the final user-facing message for a completed agent-edit turn.

    The agent ALWAYS writes the message: the LLM narrator is invoked for every
    outcome, and whatever message it produces is the final message — prose is
    never gated or replaced by a deterministic substitute. The deterministic
    fallback is used only when no agent message exists (provider failure,
    timeout, or a response that did not yield a message).

    The synthesis prompt feeds the agent the structured outcome
    (``change.graph_unchanged``, ``outcome.kind``,
    ``change.landed_operation_count``, ``validation.passed``) and requires the
    narrative to describe exactly those facts.

    Every path writes compact narrative_context.json and
    narrative_validation.json artifacts; the LLM path additionally writes
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

        # ── LLM narrator path (sole path; SD1 fast-path removed) ──────
        route = _narrator_route() or _NARRATOR_DEFAULT_ROUTE
        model = _narrator_model() or _NARRATOR_DEFAULT_MODEL

        # Pre-compute the deterministic fallback in case the LLM path
        # produces no message at all.
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

        # ── Select the message: the agent's own message ALWAYS ships. ──
        # There is no prose gate and no discard-and-replace: when the LLM
        # narrator produced a message, that message IS the final message.
        # The deterministic fallback ships only when no agent message exists.
        if llm_message is not None and fallback_reason is None:
            selected_source = "narrator"
            selected_message = llm_message
        else:
            selected_source = "fallback"
            selected_message = fallback_message
            fallback_reason = fallback_reason or "no_narrator_message"

        validation: dict[str, Any] = {
            "ok": True,
            "message": selected_message,
            "issues": [],
            "selected_source": selected_source,
            "fallback_reason": fallback_reason,
        }
        _write_narrative_artifacts(
            state,
            narrative_context,
            validation,
            request_messages=llm_request,
            llm_response=llm_response,
        )
        return selected_message

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
'''
