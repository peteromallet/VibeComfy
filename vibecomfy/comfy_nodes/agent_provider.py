from __future__ import annotations

import importlib
import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from .agent_audit import redact_closed_set
from .agent_contracts import AGENT_EDIT_TURN_CONTRACT_VERSION


LOGGER = logging.getLogger(__name__)

DEFAULT_ROUTE = "arnold"
DEFAULT_MODEL = "agent-edit"
DEFAULT_HERMES_ENV_PATH = Path("~/.hermes/.env")
SUPPORTED_BROWSER_ROUTES = ("auto", "deepseek", "anthropic", "openai-codex")

_ARNOLD_GUIDANCE = (
    "Use local Arnold/Hermes setup for this route. Configure ARNOLD_API_KEY or "
    "HERMES_API_KEY locally; browser-submitted API keys are not stored."
)
_ANTHROPIC_GUIDANCE = (
    "Anthropic/Claude runs through local Arnold/Hermes. Acknowledge the ToS in "
    "the UI and configure local ARNOLD_API_KEY or HERMES_API_KEY; browser keys "
    "are not accepted."
)
_CODEX_GUIDANCE = (
    "OpenAI Codex runs through local Arnold/Hermes. Configure local "
    "ARNOLD_API_KEY or HERMES_API_KEY; browser keys are not accepted."
)


class ProviderError(RuntimeError):
    pass


class AuthError(ProviderError):
    def __init__(self, message: str = "provider authentication failed") -> None:
        super().__init__(message)
        self.response = type("Response", (), {"status_code": 401})()


class MalformedModelJSON(ProviderError, ValueError):
    pass


class MissingRequiredField(ProviderError, ValueError):
    pass


@dataclass(frozen=True)
class AgentTurnResult:
    python: str
    message: str
    route: str
    model: str | None = None
    audit_metadata: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "python": self.python,
            "message": self.message,
            "route": self.route,
            "model": self.model,
            "audit_metadata": dict(self.audit_metadata or {}),
        }


@dataclass(frozen=True)
class BatchTurnResult:
    batch: str
    message: str
    route: str
    model: str | None = None
    audit_metadata: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch": self.batch,
            "message": self.message,
            "route": self.route,
            "model": self.model,
            "audit_metadata": dict(self.audit_metadata or {}),
        }


@dataclass(frozen=True)
class AgentRouteDescriptor:
    requested_route: str
    normalized_route: str
    browser_api_key_allowed: bool
    guidance: str | None = None
    tos_acknowledgement_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested_route": self.requested_route,
            "normalized_route": self.normalized_route,
            "browser_api_key_allowed": self.browser_api_key_allowed,
            "guidance": self.guidance,
            "tos_acknowledgement_required": self.tos_acknowledgement_required,
        }


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        match = re.search(r"```(?:json)?\s*(.*?)```", stripped, re.DOTALL)
        if match:
            stripped = match.group(1).strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise MalformedModelJSON(
            "Agent response was not valid JSON with keys `python` and `message`."
        ) from exc
    if not isinstance(parsed, dict):
        raise MalformedModelJSON("Agent response must be a JSON object.")
    return parsed


_BATCH_FENCE_RE = re.compile(r"```batch\s*\n(.*?)```", re.DOTALL)
_BATCH_RETRY_NUDGE = (
    "Your previous reply was empty or unparseable. Reply with user-facing prose "
    "(one sentence telling the user what you are doing) followed by exactly "
    "one ```batch fenced block containing your edit statements."
)


def normalize_user_message(message: str | None) -> str:
    if not isinstance(message, str):
        return ""
    return " ".join(message.strip().split())


def ensure_sentence_message(message: str | None, *, fallback: str) -> str:
    text = normalize_user_message(message)
    if not text:
        text = normalize_user_message(fallback)
    if not text:
        text = "The agent edit turn completed."
    if text[-1] not in ".!?":
        text = f"{text}."
    return text


def extract_batch_fence(text: str) -> tuple[str, str]:
    """Extract exactly one ```batch fenced block from a model response.

    Returns ``(batch_code, prose)`` where *batch_code* is the code inside the
    fence and *prose* is all text outside it (the agent's user-facing message).

    Raises :class:`MalformedModelJSON` when zero or multiple batch fences are
    found — the fence is the single stripping seam.
    """
    if not text.strip():
        raise MalformedModelJSON(
            "Agent batch_repl response was empty. Expected exactly one ```batch fenced block."
        )
    matches = _BATCH_FENCE_RE.findall(text)
    if len(matches) == 0:
        raise MalformedModelJSON(
            "Agent response does not contain a ```batch fenced block. "
            "Include exactly one ```batch code block with your edit statements."
        )
    if len(matches) > 1:
        raise MalformedModelJSON(
            "Agent response contains multiple ```batch fenced blocks. "
            "Include exactly one ```batch code block per turn."
        )
    batch_code = matches[0].strip()
    # Extract prose: everything outside the fence, with the fence text removed.
    prose = _BATCH_FENCE_RE.sub("", text).strip()
    return batch_code, prose


def build_batch_messages(
    *,
    task: str,
    turn_number: int = 0,
    python_source: str = "",
    signature_catalog: str = "",
    available_node_names: str = "",
    diff: str = "",
    report: str = "",
    budget_remaining: int = 12,
    max_batches: int = 12,
) -> list[dict[str, str]]:
    """Build messages for the batch-REPL wire protocol.

    Turn 0 includes the full Python render, in-graph typed signatures, a compact
    names-only node index, and budget. Later turns include only the diff,
    structured teaching report, remaining budget, and task — no full Python
    re-dump.

    The system prompt describes prose + a single ```batch fenced block with
    ``done()`` and ``clarify(\"...\")`` as in-batch calls.  It does **not**
    mention JSON delta response requirements.
    """
    system = (
        "You edit a ComfyUI canvas as live Python objects.\n"
        "Each node is a variable with assignable attributes; wiring reads\n"
        "`.OUTPUT` slots from other variables.\n\n"
        "Two moves:\n"
        "- Add: `x = NodeType(field=val, input=other.OUTPUT)`\n"
        "- Change: `obj.attr = value`\n\n"
        "Privileged calls:\n"
        "- `del x`\n"
        "- `node.mode = \"bypassed\" | \"muted\" | \"enabled\"`\n"
        "  (bypass does NOT pass input through)\n"
        "- `search(focus_types=[\"ClassName\"])` — query without applying\n"
        "- `done()` — commit after last successful edit\n\n"
        "Output rule:\n"
        "Always name the output slot: write `up.IMAGE`, never bare `up`.\n"
        "Bare references to multi-output or same-type-output nodes are rejected.\n\n"
        "Known limits:\n"
        "- `attr = None` disconnects a wire (not a null literal)\n"
        "- List-socket inputs, reorder/group, cross-subgraph: out of scope\n\n"
        "Use the graph's real names:\n"
        "Reference EXISTING nodes by the EXACT variable names shown in the Current\n"
        "scratchpad Python above (e.g. its decode and save nodes). NEVER invent a\n"
        "name or copy a name from the worked example below — those are placeholders.\n\n"
        "Search first (only when needed):\n"
        "The existing nodes are already shown above — do NOT search for them.\n"
        "Only `search(focus_types=[\"X\"])` for a NEW node TYPE you want to ADD and\n"
        "whose signature you don't already know. One search is enough; never repeat\n"
        "the same search. Then construct and wire the node in the SAME or next batch.\n\n"
        "Placement:\n"
        "Optional `near=anchor_var` placement hint; never set coordinates.\n\n"
        "Envelope:\n"
        "Start with user-facing prose (one sentence), then exactly one\n"
        "```batch fenced block. Never respond with only a fenced\n"
        "block — the prose is required. No JSON. One batch per turn.\n"
        "`clarify(\"...\")` is an alternate terminal when intent is\n"
        "genuinely missing.\n\n"
        f"Budget: {budget_remaining} batch(es) remaining out of {max_batches}.\n\n"
        "Worked example (PLACEHOLDER names — substitute your graph's real ones):\n"
        "Add 2x upscale after the decode node, feed the existing save node:\n"
        "```batch\n"
        "upscaled = ImageScaleBy(image=<decode_var>.IMAGE, scale_by=2.0, near=<decode_var>)\n"
        "<save_var>.images = upscaled.IMAGE\n"
        "done()\n"
        "```"
    )
    if turn_number == 0:
        catalog_block = ""
        if signature_catalog:
            catalog_block = (
                "\n\nSignatures for nodes currently in the graph:\n"
                f"```\n{signature_catalog}\n```"
            )
        names_block = ""
        if available_node_names:
            names_block = (
                "\n\nOther available node type names "
                "(search to get a signature before constructing):\n"
                f"```\n{available_node_names}\n```"
            )
        user = (
            f"User request:\n{task}\n\n"
            "Current scratchpad Python (full render):\n"
            "```python\n"
            f"{python_source}\n"
            "```"
            f"{catalog_block}"
            f"{names_block}"
        )
    else:
        diff_block = ""
        if diff:
            diff_block = f"\n\nDiff from previous render:\n```diff\n{diff}\n```"
        report_block = ""
        if report:
            report_block = f"\n\nTeaching report from previous turn:\n{report}"
        user = (
            f"User request:\n{task}\n"
            f"{diff_block}"
            f"{report_block}"
            f"\n\nBudget: {budget_remaining} batch(es) remaining out of {max_batches}."
        )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def build_messages(*, task: str, python_source: str) -> list[dict[str, str]]:
    system = (
        "You edit VibeComfy Python scratchpads for a ComfyUI canvas.\n"
        "Return only JSON with keys `python` and `message`.\n"
        "`python` must be the complete replacement file. Preserve imports, build(), "
        "metadata, node ids, and layout-related identity unless the user request "
        "requires a graph edit. Prefer simple VibeWorkflow/template API changes "
        "such as set_prompt, set_seed, set_steps, node/add_node/connect/replace_edge. "
        "Prefer direct static graph edits first. If a request can be statically lowered, "
        "lower it in ordinary graph structure instead of emitting intent nodes. "
        "Use `vibecomfy.loop` only for bounded, visible sweeps that cannot be lowered "
        "cleanly; its metadata must keep a stable `vibecomfy_uid`, `kind`, typed "
        "`io.inputs`/`io.outputs`, and a bounded loop contract (`count`/`iterations`/`over`) "
        "with at most 128 iterations. Use `vibecomfy.code` only for inspectable typed logic "
        "when no more specific shipped shape fits; its `intent.source` or `intent.spec` "
        "must stay within 16 KiB. Reject side-effecting, unbounded, runtime-only, external-I/O, "
        "or otherwise unrepresentable requests at policy level instead of pretending they queue. "
        "Editor-only intent nodes may stay on the canvas but must block Queue until lowered. "
        "When you create one programmatically, build its metadata with `intent_node_properties(...)` "
        "rather than hand-rolling properties blobs. Do not download models, run ComfyUI, use network, "
        "or include markdown fences.\n"
        "`message` should be a concise explanation for the user."
    )
    user = (
        f"User request:\n{task}\n\n"
        "Current scratchpad Python:\n"
        "```python\n"
        f"{python_source}\n"
        "```"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def build_delta_messages(
    *,
    task: str,
    projection: str,
    op_schema: Mapping[str, Any],
) -> list[dict[str, str]]:
    system = (
        "You edit a VibeComfy browser UI graph by returning typed delta operations.\n"
        "Return only JSON with keys `delta` and `message`.\n"
        "`delta` must be a list of operations that exactly follow this schema:\n"
        f"{json.dumps(op_schema, sort_keys=True)}\n"
        "Address formats — copy these shapes EXACTLY (scope_path is \"\" for root-level nodes; "
        "use the uid shown as target=[...] in the projection):\n"
        "- Node target: [scope_path, uid]            e.g. [\"\", \"352\"]\n"
        "- Field target: [scope_path, uid, field_path]  (a list of LENGTH 3)  e.g. [\"\", \"352\", \"value\"]\n"
        "- Link endpoint: [scope_path, uid, slot_or_field]  e.g. from [\"\", \"115\", \"NOISE\"] to [\"\", \"113\", \"noise\"]\n"
        "Worked example — set a node's text field (note the length-3 target):\n"
        "{\"delta\": [{\"op\": \"set_node_field\", \"target\": [\"\", \"352\", \"value\"], "
        "\"value\": \"a serene mountain lake\"}], \"message\": \"Set the prompt text.\"}\n"
        "Use only addresses that appear in the provided projection. Do not emit raw "
        "LiteGraph node or link payloads. Do not rewrite the whole workflow. If the "
        "request cannot be represented with the allowed operations, return an empty "
        "`delta` and explain the limitation in `message`."
    )
    user = (
        f"User request:\n{task}\n\n"
        "Address-preserving UI projection:\n"
        f"{projection}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _supported_browser_route_options() -> dict[str, dict[str, Any]]:
    return {
        route: _resolve_agent_route(route).to_dict()
        for route in SUPPORTED_BROWSER_ROUTES
    }


def _deepseek_key_present() -> bool:
    """True if a DeepSeek API key is available (env or ~/.hermes/.env)."""
    if os.getenv("DEEPSEEK_API_KEY"):
        return True
    try:
        env_path = Path("~/.hermes/.env").expanduser()
        if env_path.is_file():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("DEEPSEEK_API_KEY=") and line.split("=", 1)[1].strip():
                    return True
    except OSError:
        pass
    return False


def _arnold_creds_present() -> bool:
    """True if any arnold-family (Claude/OpenRouter) credential is configured."""
    return any(
        os.getenv(var)
        for var in ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "ARNOLD_API_KEY", "HERMES_API_KEY")
    )


def _resolve_agent_route(route: str | None) -> AgentRouteDescriptor:
    requested = (route or DEFAULT_ROUTE).strip().lower() or DEFAULT_ROUTE
    if requested == "claude":
        requested = "anthropic"
    elif requested == "codex":
        requested = "openai-codex"

    if requested == "auto":
        # "auto" picks the provider that actually works for agent-edit here.
        # DeepSeek is the validated, reliable agent-edit backend, so prefer it
        # whenever a DeepSeek key is present — even if an arnold-family key is ALSO
        # set (an interactive shell commonly inherits ANTHROPIC/OPENROUTER/HERMES
        # keys, and the arnold/Claude batch path has been observed to return an
        # empty response here, surfacing as MalformedModelJSON on every submit).
        # Fall back to arnold only when no DeepSeek key is available.
        if _deepseek_key_present():
            return AgentRouteDescriptor(
                requested_route=requested,
                normalized_route="deepseek",
                browser_api_key_allowed=True,
                guidance="DeepSeek browser key submission is supported and stored locally.",
            )
        return AgentRouteDescriptor(
            requested_route=requested,
            normalized_route="arnold",
            browser_api_key_allowed=False,
            guidance=_ARNOLD_GUIDANCE,
        )
    if requested == "deepseek":
        return AgentRouteDescriptor(
            requested_route=requested,
            normalized_route="deepseek",
            browser_api_key_allowed=True,
            guidance="DeepSeek browser key submission is supported and stored locally.",
        )
    if requested == "anthropic":
        return AgentRouteDescriptor(
            requested_route=requested,
            normalized_route="arnold",
            browser_api_key_allowed=False,
            guidance=_ANTHROPIC_GUIDANCE,
            tos_acknowledgement_required=True,
        )
    if requested == "openai-codex":
        return AgentRouteDescriptor(
            requested_route=requested,
            normalized_route="arnold",
            browser_api_key_allowed=False,
            guidance=_CODEX_GUIDANCE,
        )
    if requested == "arnold":
        return AgentRouteDescriptor(
            requested_route=requested,
            normalized_route="arnold",
            browser_api_key_allowed=False,
            guidance=_ARNOLD_GUIDANCE,
        )
    return AgentRouteDescriptor(
        requested_route=requested,
        normalized_route=requested,
        browser_api_key_allowed=False,
    )


def _credential_presence() -> dict[str, bool]:
    return {
        "arnold_api_key": bool(os.getenv("ARNOLD_API_KEY")),
        "hermes_api_key": bool(os.getenv("HERMES_API_KEY")),
        "deepseek_api_key": bool(os.getenv("DEEPSEEK_API_KEY")),
    }


def _non_secret_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    redacted = redact_closed_set(dict(value)).value
    return redacted if isinstance(redacted, dict) else {}


def _resolve_route_and_model(
    route: str | None,
    model: str | None,
) -> tuple[AgentRouteDescriptor, str, str]:
    route_descriptor = _resolve_agent_route(route)
    selected_route = route_descriptor.normalized_route
    selected_model = model or os.getenv("VIBECOMFY_AGENT_MODEL", DEFAULT_MODEL)
    return route_descriptor, selected_route, selected_model


def _provider_status_metadata(
    *,
    route_descriptor: AgentRouteDescriptor,
    selected_route: str,
    selected_model: str,
    provider_available: bool,
) -> dict[str, Any]:
    return {
        "route": selected_route,
        "requested_route": route_descriptor.requested_route,
        "model": selected_model,
        "provider": "arnold",
        "provider_available": provider_available,
        "contract_version": AGENT_EDIT_TURN_CONTRACT_VERSION,
        "route_metadata": route_descriptor.to_dict(),
        "route_options": _supported_browser_route_options(),
        "credential_presence": _credential_presence(),
        "legacy_deepseek_fallback_enabled": False,
    }


def _normalize_readiness_payload(
    payload: Mapping[str, Any] | None,
    *,
    provider_available: bool,
    default_reason: str,
) -> dict[str, Any]:
    runtime_payload = _non_secret_mapping(payload or {})
    ready_value = runtime_payload.get("ready")
    if ready_value is None:
        ready_value = runtime_payload.get("ok")
    ready = bool(ready_value)

    reason = runtime_payload.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        for fallback_key in ("detail", "error", "message"):
            fallback = runtime_payload.get(fallback_key)
            if isinstance(fallback, str) and fallback.strip():
                reason = fallback.strip()
                break
        else:
            reason = default_reason

    normalized = dict(runtime_payload)
    normalized.pop("ok", None)
    normalized["ready"] = ready
    normalized["reason"] = reason
    normalized["provider_available"] = provider_available
    return normalized


def _load_arnold_runtime() -> Any:
    module_name = os.getenv("VIBECOMFY_ARNOLD_RUNTIME_MODULE")
    candidates = [module_name] if module_name else [
        "arnold.hermes",
        "hermes_agent",
        "arnold",
    ]
    errors: list[str] = []
    for candidate in candidates:
        if not candidate:
            continue
        try:
            return importlib.import_module(candidate)
        except ImportError as exc:
            errors.append(f"{candidate}: {exc}")
    raise ProviderError(
        "Arnold/Hermes runtime is unavailable. Install/configure Arnold or set "
        "VIBECOMFY_ARNOLD_RUNTIME_MODULE. Import attempts: " + "; ".join(errors)
    )


def _normalize_agent_response(
    response: Any,
    *,
    route: str,
    model: str | None,
    audit_metadata: Mapping[str, Any] | None = None,
) -> AgentTurnResult:
    if isinstance(response, AgentTurnResult):
        return response
    if isinstance(response, str):
        payload = _extract_json_object(response)
    elif isinstance(response, Mapping):
        payload = dict(response)
        content = payload.get("content")
        if isinstance(content, str) and "python" not in payload:
            payload = _extract_json_object(content)
    else:
        raise MalformedModelJSON("Agent response must be a JSON string or object.")

    python = payload.get("python")
    message = payload.get("message")
    if not isinstance(python, str):
        raise MissingRequiredField("Agent JSON must include string key `python`.")
    if not isinstance(message, str):
        raise MissingRequiredField("Agent JSON must include string key `message`.")
    return AgentTurnResult(
        python=python,
        message=message,
        route=route,
        model=model,
        audit_metadata=audit_metadata or {},
    )


def _call_runtime(runtime: Any, *, task: str, python_source: str, route: str, model: str | None) -> Any:
    messages = build_messages(task=task, python_source=python_source)
    if hasattr(runtime, "run_agent_turn"):
        return runtime.run_agent_turn(
            task=task,
            python_source=python_source,
            route=route,
            model=model,
            messages=messages,
        )
    if hasattr(runtime, "run"):
        return runtime.run(
            task=task,
            python_source=python_source,
            route=route,
            model=model,
            messages=messages,
        )
    raise ProviderError("Arnold/Hermes runtime does not expose run_agent_turn or run.")


def _call_delta_runtime(
    runtime: Any,
    *,
    task: str,
    projection: str,
    op_schema: Mapping[str, Any],
    route: str,
    model: str | None,
) -> Any:
    messages = build_delta_messages(task=task, projection=projection, op_schema=op_schema)
    if hasattr(runtime, "run_agent_turn_delta"):
        return runtime.run_agent_turn_delta(
            task=task,
            projection=projection,
            op_schema=op_schema,
            route=route,
            model=model,
            messages=messages,
        )
    if hasattr(runtime, "run_delta_agent_turn"):
        return runtime.run_delta_agent_turn(
            task=task,
            projection=projection,
            op_schema=op_schema,
            route=route,
            model=model,
            messages=messages,
        )
    if hasattr(runtime, "run"):
        return runtime.run(
            task=task,
            projection=projection,
            op_schema=op_schema,
            route=route,
            model=model,
            messages=messages,
            response_contract="delta",
        )
    raise ProviderError("Arnold/Hermes runtime does not expose run_agent_turn_delta or run.")


def run_agent_turn(
    task: str,
    python_source: str,
    *,
    route: str | None = None,
    model: str | None = None,
) -> AgentTurnResult:
    route_descriptor = _resolve_agent_route(route)
    selected_route = route_descriptor.normalized_route
    selected_model = model or os.getenv("VIBECOMFY_AGENT_MODEL", DEFAULT_MODEL)
    runtime = _load_arnold_runtime()
    try:
        response = _call_runtime(
            runtime,
            task=task,
            python_source=python_source,
            route=selected_route,
            model=selected_model,
        )
    except PermissionError as exc:
        raise AuthError(str(exc)) from exc
    except TimeoutError:
        raise
    except (ProviderError, MalformedModelJSON, MissingRequiredField):
        raise
    except Exception as exc:
        raise ProviderError(str(exc)) from exc
    return _normalize_agent_response(
        response,
        route=selected_route,
        model=selected_model,
        audit_metadata={
            "provider": "arnold",
            "requested_route": route_descriptor.requested_route,
            "route_metadata": route_descriptor.to_dict(),
            "legacy_deepseek_fallback_enabled": False,
            "credential_presence": _credential_presence(),
        },
    )


def run_agent_turn_delta(
    task: str,
    projection: str,
    *,
    op_schema: Mapping[str, Any] | None = None,
    route: str | None = None,
    model: str | None = None,
):
    from vibecomfy.porting.edit_ops import (
        EDIT_OP_RESPONSE_SCHEMA_V2,
        EditOpParseError,
        normalize_delta_agent_response,
    )

    route_descriptor = _resolve_agent_route(route)
    selected_route = route_descriptor.normalized_route
    selected_model = model or os.getenv("VIBECOMFY_AGENT_MODEL", DEFAULT_MODEL)
    schema = op_schema or EDIT_OP_RESPONSE_SCHEMA_V2
    runtime = _load_arnold_runtime()
    try:
        response = _call_delta_runtime(
            runtime,
            task=task,
            projection=projection,
            op_schema=schema,
            route=selected_route,
            model=selected_model,
        )
    except PermissionError as exc:
        raise AuthError(str(exc)) from exc
    except TimeoutError:
        raise
    except (ProviderError, MalformedModelJSON, MissingRequiredField):
        raise
    except Exception as exc:
        raise ProviderError(str(exc)) from exc
    try:
        return normalize_delta_agent_response(
            response,
            route=selected_route,
            model=selected_model,
            audit_metadata={
                "provider": "arnold",
                "requested_route": route_descriptor.requested_route,
                "route_metadata": route_descriptor.to_dict(),
                "legacy_deepseek_fallback_enabled": False,
                "credential_presence": _credential_presence(),
                "response_contract": "delta",
            },
        )
    except EditOpParseError as exc:
        raise MalformedModelJSON(str(exc)) from exc


def _normalize_batch_response(
    response: Any,
    *,
    route: str,
    model: str | None,
    audit_metadata: Mapping[str, Any] | None = None,
) -> BatchTurnResult:
    """Normalize a raw runtime response into a :class:`BatchTurnResult`.

    Extracts the ```batch fenced block and surrounding prose via
    :func:`extract_batch_fence`.  The runtime may return a string (the raw
    model response) or a mapping with a ``content`` key.
    """
    if isinstance(response, BatchTurnResult):
        return response
    if isinstance(response, str):
        text = response
    elif isinstance(response, Mapping):
        payload = dict(response)
        content = payload.get("content")
        if isinstance(content, str) and "batch" not in payload:
            text = content
        elif isinstance(payload.get("batch"), str):
            batch_code = payload["batch"]
            message = normalize_user_message(payload.get("message", ""))
            return BatchTurnResult(
                batch=batch_code,
                message=message,
                route=route,
                model=model,
                audit_metadata=audit_metadata or {},
            )
        else:
            text = str(response)
    else:
        raise MalformedModelJSON("Agent response must be a string or object.")
    if not text.strip():
        raise MalformedModelJSON(
            "Agent batch_repl response was empty. Expected exactly one ```batch fenced block."
        )
    batch_code, prose = extract_batch_fence(text)
    # Preserve prose as-is (possibly empty); the backend synthesizer
    # (_synthesize_batch_repl_message) owns final message filling.
    message = prose.strip()
    return BatchTurnResult(
        batch=batch_code,
        message=message,
        route=route,
        model=model,
        audit_metadata=audit_metadata or {},
    )


def _call_batch_runtime(
    runtime: Any,
    *,
    task: str,
    messages: list[dict[str, str]],
    route: str,
    model: str | None,
) -> Any:
    """Call the Arnold/Hermes runtime for a batch-REPL turn."""
    if hasattr(runtime, "run_agent_turn_batch"):
        return runtime.run_agent_turn_batch(
            task=task,
            route=route,
            model=model,
            messages=messages,
        )
    if hasattr(runtime, "run_agent_turn"):
        return runtime.run_agent_turn(
            task=task,
            python_source="",
            route=route,
            model=model,
            messages=messages,
        )
    if hasattr(runtime, "run"):
        return runtime.run(
            task=task,
            route=route,
            model=model,
            messages=messages,
            response_contract="batch_repl",
        )
    raise ProviderError(
        "Arnold/Hermes runtime does not expose run_agent_turn_batch, "
        "run_agent_turn, or run."
    )


def run_agent_turn_batch(
    task: str,
    messages: list[dict[str, str]],
    *,
    route: str | None = None,
    model: str | None = None,
) -> BatchTurnResult:
    """Run a single batch-REPL turn through the Arnold/Hermes provider.

    Sends *messages* (built by :func:`build_batch_messages`) to the model
    and normalizes the response through :func:`extract_batch_fence` instead
    of JSON parsing.  Returns a :class:`BatchTurnResult` with the fenced
    batch code and surrounding prose.

    Parameters
    ----------
    task:
        The user's natural-language edit request.
    messages:
        Pre-built chat messages from :func:`build_batch_messages`.
    route:
        Optional provider route name.  Resolved via :func:`_resolve_agent_route`.
    model:
        Optional model identifier.  Falls back to ``VIBECOMFY_AGENT_MODEL``.
    """
    route_descriptor = _resolve_agent_route(route)
    selected_route = route_descriptor.normalized_route
    selected_model = model or os.getenv("VIBECOMFY_AGENT_MODEL", DEFAULT_MODEL)
    runtime = _load_arnold_runtime()
    audit_metadata: dict[str, Any] = {
        "provider": "arnold",
        "requested_route": route_descriptor.requested_route,
        "route_metadata": route_descriptor.to_dict(),
        "legacy_deepseek_fallback_enabled": False,
        "credential_presence": _credential_presence(),
        "response_contract": "batch_repl",
    }
    last_malformed: MalformedModelJSON | None = None
    # 1 initial + 2 retries: DeepSeek intermittently returns an empty / no-fence
    # response that parses as MalformedModelJSON; the same prompt usually succeeds
    # on a later attempt.
    for attempt in range(3):
        attempt_messages = messages if attempt == 0 else [*messages, {"role": "system", "content": _BATCH_RETRY_NUDGE}]
        try:
            response = _call_batch_runtime(
                runtime,
                task=task,
                messages=attempt_messages,
                route=selected_route,
                model=selected_model,
            )
            metadata = dict(audit_metadata)
            if attempt:
                metadata["batch_repl_retry"] = {
                    "count": attempt,
                    "reason": str(last_malformed) if last_malformed else "malformed batch response",
                }
            return _normalize_batch_response(
                response,
                route=selected_route,
                model=selected_model,
                audit_metadata=metadata,
            )
        except PermissionError as exc:
            raise AuthError(str(exc)) from exc
        except TimeoutError:
            raise
        except MalformedModelJSON as exc:
            if attempt < 2:
                last_malformed = exc
                LOGGER.warning(
                    "Retrying batch_repl agent turn after malformed model response: %s",
                    exc,
                )
                continue
            raise
        except (ProviderError, MissingRequiredField):
            raise
        except Exception as exc:
            raise ProviderError(str(exc)) from exc
    raise last_malformed or MalformedModelJSON("Agent batch_repl response was malformed.")


def readiness(*, route: str | None = None, model: str | None = None) -> dict[str, Any]:
    route_descriptor, selected_route, selected_model = _resolve_route_and_model(route, model)
    try:
        runtime = _load_arnold_runtime()
    except ProviderError as exc:
        return {
            **_provider_status_metadata(
                route_descriptor=route_descriptor,
                selected_route=selected_route,
                selected_model=selected_model,
                provider_available=False,
            ),
            "ready": False,
            "reason": str(exc),
            "error": str(exc),
        }

    readiness_fn: Callable[..., Any] | None = getattr(runtime, "readiness", None)
    if callable(readiness_fn):
        raw_status = readiness_fn(route=selected_route, model=selected_model)
    else:
        status_fn: Callable[..., Any] | None = getattr(runtime, "get_agent_status", None)
        raw_status = status_fn(route=selected_route, model=selected_model) if status_fn else {}
    if not isinstance(raw_status, Mapping):
        raw_status = {}

    return {
        **_normalize_readiness_payload(
            raw_status,
            provider_available=True,
            default_reason="Provider ready." if raw_status.get("ok", True) else "Provider is unavailable.",
        ),
        **_provider_status_metadata(
            route_descriptor=route_descriptor,
            selected_route=selected_route,
            selected_model=selected_model,
            provider_available=True,
        ),
    }


def get_agent_status(*, route: str | None = None, model: str | None = None) -> dict[str, Any]:
    readiness_payload = readiness(route=route, model=model)
    ready = bool(readiness_payload.get("ready"))
    status = {
        **readiness_payload,
        "ok": ready,
        "readiness": "ready" if ready else "unavailable",
    }
    if not ready and not status.get("provider_available") and "error" not in status:
        status["error"] = str(status.get("reason") or "Provider is unavailable.")
    return status


def _hermes_env_path(path: Path | None = None) -> Path:
    return (path or DEFAULT_HERMES_ENV_PATH).expanduser()


def save_deepseek_api_key(api_key: str, *, env_path: Path | None = None) -> dict[str, Any]:
    if not isinstance(api_key, str) or not api_key.strip():
        raise ValueError("DeepSeek API key must be a non-empty string.")
    target = _hermes_env_path(env_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    try:
        lines = target.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        lines = []
    replaced = False
    rendered: list[str] = []
    for line in lines:
        if line.startswith("DEEPSEEK_API_KEY="):
            rendered.append(f"DEEPSEEK_API_KEY={api_key.strip()}")
            replaced = True
        else:
            rendered.append(line)
    if not replaced:
        rendered.append(f"DEEPSEEK_API_KEY={api_key.strip()}")
    tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    tmp.write_text("\n".join(rendered).rstrip("\n") + "\n", encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    tmp.replace(target)
    return {
        "ok": True,
        "stored": True,
        "provider": "deepseek",
        "key_name": "DEEPSEEK_API_KEY",
        "path": str(target),
    }


def handle_credential_submission(
    payload: Mapping[str, Any],
    *,
    env_path: Path | None = None,
) -> dict[str, Any]:
    requested_route = str(payload.get("provider") or payload.get("route") or "").lower() or None
    route_descriptor = _resolve_agent_route(requested_route)
    provider = route_descriptor.requested_route
    deepseek_key = payload.get("deepseek_api_key")
    api_key = payload.get("api_key")
    if isinstance(deepseek_key, str) and (
        route_descriptor.normalized_route == "deepseek" or requested_route is None
    ):
        return save_deepseek_api_key(deepseek_key, env_path=env_path)
    if (
        route_descriptor.normalized_route == "deepseek"
        and route_descriptor.browser_api_key_allowed
        and isinstance(api_key, str)
    ):
        return save_deepseek_api_key(api_key, env_path=env_path)
    if (
        provider in {"auto", "arnold", "anthropic", "openai-codex"}
        or "claude_api_key" in payload
        or "codex_api_key" in payload
        or "openai_api_key" in payload
    ):
        return {
            "ok": True,
            "stored": False,
            "provider": route_descriptor.normalized_route,
            "requested_route": route_descriptor.requested_route,
            "route_metadata": route_descriptor.to_dict(),
            "ignored": True,
            "reason": route_descriptor.guidance or _ARNOLD_GUIDANCE,
        }
    return {
        "ok": False,
        "stored": False,
        "provider": provider or "unknown",
        "ignored": True,
        "reason": "No supported S1 credential was submitted.",
    }


__all__ = [
    "AgentTurnResult",
    "AuthError",
    "BatchTurnResult",
    "MalformedModelJSON",
    "MissingRequiredField",
    "ProviderError",
    "_load_arnold_runtime",
    "build_batch_messages",
    "build_delta_messages",
    "build_messages",
    "ensure_sentence_message",
    "extract_batch_fence",
    "readiness",
    "get_agent_status",
    "handle_credential_submission",
    "normalize_user_message",
    "run_agent_turn_batch",
    "run_agent_turn_delta",
    "run_agent_turn",
    "save_deepseek_api_key",
]
