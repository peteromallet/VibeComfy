"""Contracts for the headless VibeComfy agent CLI/API surface.

These types are intentionally separate from :class:`vibecomfy.executor.contracts.ExecutorRequest`
so that headless-only concerns (output directory, live/dry-run/apply flags, timeouts) do not
leak into the frozen HTTP executor contract.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from vibecomfy.executor.stage_contracts import NeedsInput


def _require_optional_str(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"HeadlessAgentRequest `{field_name}` must be a string or null.")
    return value


def _parse_bool(value: Any, *, field_name: str, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise ValueError(f"HeadlessAgentRequest `{field_name}` must be a boolean.")


def _parse_extra(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("HeadlessAgentRequest `extra` must be a mapping or null.")
    return dict(value)


def _load_workflow_graph(path: str | Path) -> dict[str, Any]:
    workflow_path = Path(path)
    if not workflow_path.is_file():
        raise ValueError(f"Workflow file not found: {workflow_path}")
    try:
        data = json.loads(workflow_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Workflow file is not valid JSON: {workflow_path}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Workflow file must contain a JSON object: {workflow_path}")
    return data


@dataclass(frozen=True)
class HeadlessAgentRequest:
    """Headless request shape for ``python -m vibecomfy.agent``.

    ``query`` is the only required field.  The graph may be supplied as a dict
    or loaded from a JSON file by the CLI.  Provider/model routing is resolved
    from the executor profile, not from new fields on this contract.

    Flags
    -----
    * ``live=True`` allows real model calls (still gated by provider readiness).
    * ``dry_run=True`` forces classify-only execution: no research, implement,
      or reply phases run, but the classification decision is still produced
      by a model call unless the profile/classifier short-circuits.
    * ``apply=True`` marks the caller's intent to apply an edited graph when
      the executor produces a candidate.  It does not bypass eligibility gates.
    * ``network=True`` permits research phases to call external services.
    * ``timeout`` overrides the default per-turn timeout when supported.
    * ``additive=True`` marks the request as an additive restore (the caller
      intentionally removed a feature and now asks to re-add it).  This is an
      explicit signal to the revise pipeline: the only guard it relaxes is the
      pre-edit "input graph has dangling/absent endpoints -> refuse to compound"
      precondition, and only when the dangling/absent endpoints are exactly the
      gap the requested node would fill.  All post-edit IR-compile validation,
      the collateral fence, and every gate in ``gates.py`` remain enforced.
    """

    query: str
    graph: dict[str, Any] | None = None
    workflow_id: str | None = None
    session_id: str | None = None
    profile: str | None = None
    idempotency_key: str | None = None
    output_dir: Path | str | None = None
    live: bool = True
    dry_run: bool = False
    apply: bool = False
    network: bool = True
    timeout: float | None = None
    additive: bool = False
    # Explicit interaction contract for diagnosis/advice turns:
    # ``"answer_only"`` declares that this interaction must never produce a
    # graph edit (the executor routes to agent-owned research + semantic
    # reply regardless of classification).  Deliberately NOT inferred from
    # ``apply`` — that flag only says whether a candidate is applied, not
    # whether editing is permitted.  None = ordinary interaction.
    interaction_mode: str | None = None
    # Scenario assessment contract forwarded into ExecutorRequest/classify.
    expect_graph_changed: bool | None = None
    # Batch-REPL per-request turn budget (PR-D).  Integer 1..250; None =
    # default 50.  Forwarded through to_executor_request → implement payload.
    max_batches: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.query, str) or not self.query.strip():
            raise ValueError("HeadlessAgentRequest requires a non-empty string `query`.")
        graph = self.graph
        if graph is not None and not isinstance(graph, dict):
            raise ValueError("HeadlessAgentRequest `graph` must be a dict or null.")
        if self.output_dir is not None and not isinstance(self.output_dir, (str, Path)):
            raise ValueError("HeadlessAgentRequest `output_dir` must be a string/Path or null.")
        if self.timeout is not None:
            try:
                timeout = float(self.timeout)
            except (TypeError, ValueError) as exc:
                raise ValueError("HeadlessAgentRequest `timeout` must be a number.") from exc
            if timeout <= 0:
                raise ValueError("HeadlessAgentRequest `timeout` must be greater than zero.")
            object.__setattr__(self, "timeout", timeout)
        object.__setattr__(self, "query", self.query.strip())
        object.__setattr__(self, "workflow_id", _require_optional_str(self.workflow_id, field_name="workflow_id"))
        object.__setattr__(self, "session_id", _require_optional_str(self.session_id, field_name="session_id"))
        object.__setattr__(self, "profile", _require_optional_str(self.profile, field_name="profile"))
        object.__setattr__(
            self,
            "idempotency_key",
            _require_optional_str(self.idempotency_key, field_name="idempotency_key"),
        )
        if not isinstance(self.live, bool):
            raise ValueError("HeadlessAgentRequest `live` must be a boolean.")
        if not isinstance(self.dry_run, bool):
            raise ValueError("HeadlessAgentRequest `dry_run` must be a boolean.")
        if not isinstance(self.apply, bool):
            raise ValueError("HeadlessAgentRequest `apply` must be a boolean.")
        if not isinstance(self.network, bool):
            raise ValueError("HeadlessAgentRequest `network` must be a boolean.")
        if not isinstance(self.additive, bool):
            raise ValueError("HeadlessAgentRequest `additive` must be a boolean.")
        if self.interaction_mode is not None and not isinstance(self.interaction_mode, str):
            raise ValueError(
                "HeadlessAgentRequest `interaction_mode` must be a string or null."
            )
        if self.expect_graph_changed is not None and not isinstance(
            self.expect_graph_changed, bool
        ):
            raise ValueError(
                "HeadlessAgentRequest `expect_graph_changed` must be a boolean or null."
            )
        if self.max_batches is not None:
            from vibecomfy.executor.contracts import coerce_max_batches  # noqa: PLC0415

            object.__setattr__(
                self,
                "max_batches",
                coerce_max_batches(self.max_batches, field_name="max_batches"),
            )
        object.__setattr__(self, "extra", dict(self.extra or {}))

    @property
    def output_dir_path(self) -> Path | None:
        if self.output_dir is None:
            return None
        return Path(self.output_dir)

    def to_executor_request(self) -> Any:
        """Return a frozen :class:`ExecutorRequest` from this headless request."""
        from vibecomfy.executor.contracts import ExecutorRequest  # noqa: PLC0415
        from vibecomfy.comfy_nodes.agent.session import normalize_session_id  # noqa: PLC0415

        session_id = self.session_id
        if session_id is not None:
            session_id = normalize_session_id(session_id)

        return ExecutorRequest(
            query=self.query,
            graph=self.graph,
            workflow_id=self.workflow_id,
            session_id=session_id,
            profile=self.profile,
            idempotency_key=self.idempotency_key,
            interaction_mode=self.interaction_mode,
            expect_graph_changed=self.expect_graph_changed,
            max_batches=self.max_batches,
        )

    def resolve_provider_readiness_kwargs(self, *, stage: str = "classify") -> dict[str, str | None]:
        """Resolve provider readiness arguments from the configured executor profile."""
        from vibecomfy.executor.profiles import load_profile  # noqa: PLC0415

        profile = load_profile(self.profile or "default")
        spec = profile[stage]
        return {
            "route": getattr(spec, "agent", "auto"),
            "model": getattr(spec, "model", None),
        }

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "query": self.query,
            "live": self.live,
            "dry_run": self.dry_run,
            "apply": self.apply,
            "network": self.network,
            "additive": self.additive,
        }
        if self.graph is not None:
            payload["graph"] = self.graph
        if self.workflow_id is not None:
            payload["workflow_id"] = self.workflow_id
        if self.session_id is not None:
            payload["session_id"] = self.session_id
        if self.profile is not None:
            payload["profile"] = self.profile
        if self.idempotency_key is not None:
            payload["idempotency_key"] = self.idempotency_key
        if self.output_dir is not None:
            payload["output_dir"] = str(self.output_dir)
        if self.timeout is not None:
            payload["timeout"] = self.timeout
        if self.interaction_mode is not None:
            payload["interaction_mode"] = self.interaction_mode
        if self.expect_graph_changed is not None:
            payload["expect_graph_changed"] = self.expect_graph_changed
        if self.max_batches is not None:
            payload["max_batches"] = self.max_batches
        if self.extra:
            payload["extra"] = dict(self.extra)
        return payload

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "HeadlessAgentRequest":
        from vibecomfy.executor.contracts import coerce_max_batches  # noqa: PLC0415

        if not isinstance(payload, Mapping):
            raise ValueError("HeadlessAgentRequest payload must be a mapping.")
        query = payload.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("HeadlessAgentRequest requires a non-empty string `query`.")
        graph = payload.get("graph")
        workflow_path = payload.get("workflow_path", payload.get("workflow"))
        if graph is not None and workflow_path is not None:
            raise ValueError("HeadlessAgentRequest accepts either `graph` or `workflow_path`, not both.")
        if workflow_path is not None:
            if not isinstance(workflow_path, (str, Path)):
                raise ValueError("HeadlessAgentRequest `workflow_path` must be a string/Path or null.")
            graph = _load_workflow_graph(workflow_path)
        if graph is not None and not isinstance(graph, dict):
            raise ValueError("HeadlessAgentRequest `graph` must be a dict or null.")
        output_dir = payload.get("output_dir")
        if output_dir is not None and not isinstance(output_dir, (str, Path)):
            raise ValueError("HeadlessAgentRequest `output_dir` must be a string/Path or null.")
        timeout = payload.get("timeout")
        if timeout is not None:
            try:
                timeout = float(timeout)
            except (TypeError, ValueError) as exc:
                raise ValueError("HeadlessAgentRequest `timeout` must be a number.") from exc
            if timeout <= 0:
                raise ValueError("HeadlessAgentRequest `timeout` must be greater than zero.")
        return cls(
            query=query.strip(),
            graph=graph,
            workflow_id=_require_optional_str(payload.get("workflow_id"), field_name="workflow_id"),
            session_id=_require_optional_str(payload.get("session_id"), field_name="session_id"),
            profile=_require_optional_str(payload.get("profile"), field_name="profile"),
            idempotency_key=_require_optional_str(
                payload.get("idempotency_key"),
                field_name="idempotency_key",
            ),
            output_dir=output_dir,
            live=_parse_bool(payload.get("live"), field_name="live", default=True),
            dry_run=_parse_bool(payload.get("dry_run"), field_name="dry_run", default=False),
            apply=_parse_bool(payload.get("apply"), field_name="apply", default=False),
            network=_parse_bool(payload.get("network"), field_name="network", default=True),
            timeout=timeout,
            additive=_parse_bool(payload.get("additive"), field_name="additive", default=False),
            interaction_mode=_require_optional_str(
                payload.get("interaction_mode"),
                field_name="interaction_mode",
            ),
            expect_graph_changed=_parse_bool(
                payload.get("expect_graph_changed"),
                field_name="expect_graph_changed",
                default=False,
            ) if "expect_graph_changed" in payload else None,
            max_batches=coerce_max_batches(
                payload.get("max_batches"),
                field_name="max_batches",
            ),
            extra=_parse_extra(payload.get("extra")),
        )


__all__ = ["HeadlessAgentRequest", "NeedsInput"]
