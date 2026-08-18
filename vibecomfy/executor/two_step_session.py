"""Two-step execute-session authority (B03).

The two-step pipeline replaces the full-mode research → implement → reply
phases with a single bounded *execute* phase that may run over several model
continuations for ONE logical user message.  That phase needs a durable,
thread-continuous session so a follow-up message in the same chat window can
reference work (accepted Δ, lens facts, evidence) produced by earlier turns,
without provider-native memory.

This module is the single authority for that session.  It is deliberately NOT
an in-memory dict: the source of truth is a compact, append-only execute
transcript (JSON Lines) written under the *existing* durable session directory
(``out/editor_sessions/<session_id>/``) and guarded by the process-safe
:class:`~vibecomfy.comfy_nodes.agent.session.SessionStateLock` that the agent
edit path already uses.  Reconstruction happens only through the named ingest
door (:meth:`TwoStepSessionStore.ingest_transcript`) followed by canonical Δ
replay (:meth:`TwoStepSessionStore.replay_workflow`); the in-process
:class:`EditSessionCache` is a rehydratable cache only — eviction drops the
cache, never the durable transcript.

Typed errors distinguish the failure modes the loop must surface *before* any
model work:

* ``invalid_request``        — a two-step message arrived without a session id.
* ``session_expired``        — the chat window id is closed/expired; never
                               silently minted into a fresh session.
* ``stale_message``          — the message's baseline no longer matches the
                               retained workflow revision (CAS precursor).
* ``concurrent_message``     — another message for the same session is still
                               in flight (detected via the in-flight marker).
* ``missing_delta_reference`` — a final contract cites a Δ id that is not in
                               the session's accumulated accepted-Δ ledger.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

from vibecomfy.comfy_nodes.agent.session import (
    DEFAULT_LOCK_TIMEOUT_SECONDS,
    SessionStateLock,
    normalize_session_id,
    session_dir_for,
)
from vibecomfy.executor.tool_specs import RESEARCH_PHASE_TOOLS
from vibecomfy.executor.two_step import SessionBudget

LOGGER = logging.getLogger(__name__)

# ── Durable layout ───────────────────────────────────────────────────────────

DEFAULT_TWO_STEP_SESSION_ROOT = Path("out/editor_sessions")
TWO_STEP_TRANSCRIPT_NAME = "two_step_execute.jsonl"
TWO_STEP_BASE_GRAPH_NAME = "two_step_base_graph.json"
TWO_STEP_WORKFLOW_NAME = "two_step_workflow.json"
TWO_STEP_IN_FLIGHT_NAME = ".two_step_in_flight"
TWO_STEP_OUTCOMES_NAME = "two_step_outcomes.jsonl"

# ── Typed error kinds ────────────────────────────────────────────────────────

ERROR_INVALID_REQUEST = "invalid_request"
ERROR_SESSION_EXPIRED = "session_expired"
ERROR_STALE_MESSAGE = "stale_message"
ERROR_CONCURRENT_MESSAGE = "concurrent_message"
ERROR_MISSING_DELTA_REFERENCE = "missing_delta_reference"

_TWO_STEP_ERROR_KINDS = frozenset(
    {
        ERROR_INVALID_REQUEST,
        ERROR_SESSION_EXPIRED,
        ERROR_STALE_MESSAGE,
        ERROR_CONCURRENT_MESSAGE,
        ERROR_MISSING_DELTA_REFERENCE,
    }
)


class TwoStepSessionError(Exception):
    """Typed two-step session failure (see module docstring for the kinds)."""

    def __init__(
        self,
        kind: str,
        message: str,
        *,
        session_id: str | None = None,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        if kind not in _TWO_STEP_ERROR_KINDS:
            raise ValueError(f"Unknown two-step session error kind {kind!r}.")
        super().__init__(message)
        self.kind = kind
        self.session_id = session_id
        self.detail = dict(detail or {})


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def mint_lease_token() -> str:
    """A fresh, collision-resistant lease token for one whole-turn session lease.

    Used when a message arrives without an idempotency key: the session still
    holds a durable in-flight lease (scoped to this token) so a concurrent
    message for the same session can be detected, and ``end_message`` can
    release exactly the lease this turn acquired.
    """
    return f"anon:{uuid.uuid4().hex}"


def _jsonish(value: Any) -> Any:
    """Coerce *value* to a JSON-safe primitive (best-effort, non-lossy-ish).

    Dataclasses/exceptions map to their ``__dict__``-like shape; ``Mapping`` /
    sequences recurse; anything else is ``str()``-fallback.  Used only for the
    durable completed-outcome record, never for the authoritative transcript.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return {str(k): _jsonish(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonish(item) for item in value]
    if isinstance(value, BaseException):
        return {
            "type": type(value).__name__,
            "message": str(value),
        }
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            return _jsonish(to_dict())
        except Exception:  # noqa: BLE001
            pass
    if hasattr(value, "__dict__"):
        return {str(k): _jsonish(v) for k, v in vars(value).items()}
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)


# ── Research-attempt derivation ──────────────────────────────────────────────
#
# ``research_attempt`` is a Python-derived statement of what research actually
# DID (from the session's evidence ledger), never a model judgment:
#   * never    — no research-phase tool was ever invoked in this session.
#   * empty    — research tools ran but recorded zero evidence ids.
#   * thin     — evidence ids exist but they are only search *hits*.
#   * grounded — at least one resolved record (hivemind_get / node_schema /
#                registry_lookup / ready_template_load) backs the evidence.

_GROUNDING_TOOLS = frozenset(
    {"hivemind_get", "node_schema", "registry_lookup", "ready_template_load"}
)


def derive_research_attempt(evidence_ledger: Any) -> str:
    """Derive ``never``/``empty``/``thin``/``grounded`` from an evidence ledger.

    *evidence_ledger* is any iterable of per-call entries; each entry must be a
    mapping with a ``tool`` name and an ``evidence_ids`` sequence.
    """
    entries = [e for e in evidence_ledger if isinstance(e, Mapping)]
    research_entries = [e for e in entries if e.get("tool") in RESEARCH_PHASE_TOOLS]
    if not research_entries:
        return "never"
    evidence_ids: list[str] = []
    for entry in research_entries:
        ids = entry.get("evidence_ids") or ()
        if isinstance(ids, (list, tuple)):
            evidence_ids.extend(str(i) for i in ids if i)
    if not evidence_ids:
        return "empty"
    grounded = any(e.get("tool") in _GROUNDING_TOOLS for e in research_entries)
    return "grounded" if grounded else "thin"


# ── Session state ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TwoStepSessionState:
    """Reconstructed snapshot of one two-step execute session.

    Every field is derivable from the append-only transcript; this dataclass is
    the rehydrated *view*, never the authority.
    """

    session_id: str
    route_history: tuple[dict[str, Any], ...] = ()
    accepted_delta_refs: tuple[dict[str, Any], ...] = ()
    lens_facts: tuple[dict[str, Any], ...] = ()
    evidence_ledger: tuple[dict[str, Any], ...] = ()
    replies: tuple[dict[str, Any], ...] = ()
    budget: SessionBudget = field(default_factory=SessionBudget)
    messages: tuple[dict[str, Any], ...] = ()
    last_workflow_hash: str | None = None
    closed: bool = False
    created_at: str = ""
    updated_at: str = ""

    # -- queries -------------------------------------------------------------

    def accepted_delta_ids(self) -> tuple[str, ...]:
        ids: list[str] = []
        for ref in self.accepted_delta_refs:
            for delta_id in (ref.get("delta_ids") or ()):
                if delta_id:
                    ids.append(str(delta_id))
        return tuple(ids)

    def lens_fact_ids(self) -> tuple[str, ...]:
        ids: list[str] = []
        for fact in self.lens_facts:
            for fact_id in (fact.get("fact_ids") or ()):
                if fact_id:
                    ids.append(str(fact_id))
        return tuple(ids)

    def evidence_ids(self) -> tuple[str, ...]:
        ids: list[str] = []
        for entry in self.evidence_ledger:
            for evidence_id in (entry.get("evidence_ids") or ()):
                if evidence_id:
                    ids.append(str(evidence_id))
        return tuple(ids)

    def research_attempt(self) -> str:
        return derive_research_attempt(self.evidence_ledger)

    def validate_delta_references(self, delta_ids: Any) -> None:
        """Raise :class:`TwoStepSessionError` when *delta_ids* cites a Δ id that
        is not in this session's accumulated accepted-Δ ledger (fail closed)."""
        accepted = set(self.accepted_delta_ids())
        for delta_id in delta_ids or ():
            if delta_id and str(delta_id) not in accepted:
                raise TwoStepSessionError(
                    ERROR_MISSING_DELTA_REFERENCE,
                    f"delta id {delta_id!r} is not an accepted Δ in session "
                    f"{self.session_id!r}.",
                    session_id=self.session_id,
                    detail={"delta_id": str(delta_id), "accepted": sorted(accepted)},
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "route_history": list(self.route_history),
            "accepted_delta_refs": list(self.accepted_delta_refs),
            "lens_facts": list(self.lens_facts),
            "evidence_ledger": list(self.evidence_ledger),
            "replies": list(self.replies),
            "budget": self.budget.to_dict(),
            "messages": list(self.messages),
            "last_workflow_hash": self.last_workflow_hash,
            "closed": self.closed,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TwoStepSessionState":
        return cls(
            session_id=str(data.get("session_id") or ""),
            route_history=tuple(
                d for d in (data.get("route_history") or ()) if isinstance(d, Mapping)
            ),
            accepted_delta_refs=tuple(
                d for d in (data.get("accepted_delta_refs") or ()) if isinstance(d, Mapping)
            ),
            lens_facts=tuple(
                d for d in (data.get("lens_facts") or ()) if isinstance(d, Mapping)
            ),
            evidence_ledger=tuple(
                d for d in (data.get("evidence_ledger") or ()) if isinstance(d, Mapping)
            ),
            replies=tuple(
                d for d in (data.get("replies") or ()) if isinstance(d, Mapping)
            ),
            budget=SessionBudget.from_dict(data.get("budget") or {}),
            messages=tuple(
                d for d in (data.get("messages") or ()) if isinstance(d, Mapping)
            ),
            last_workflow_hash=(
                str(data["last_workflow_hash"]) if data.get("last_workflow_hash") else None
            ),
            closed=bool(data.get("closed")),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or ""),
        )


def fresh_state(session_id: str, *, now_iso: str | None = None) -> TwoStepSessionState:
    ts = now_iso or _now_iso()
    return TwoStepSessionState(
        session_id=session_id,
        budget=SessionBudget(),
        created_at=ts,
        updated_at=ts,
    )


# ── In-process cache (LRU + idle eviction) ───────────────────────────────────

DEFAULT_IDLE_TTL_SECONDS = 900.0  # 15 minutes
DEFAULT_MAX_CACHE_ENTRIES = 128


class EditSessionCache:
    """Bounded LRU cache of rehydrated :class:`TwoStepSessionState` views.

    Idle entries (no ``get`` touch for ``idle_ttl_seconds``) are evicted on
    access/insert.  Eviction drops ONLY the cache — the durable transcript is
    always rehydratable via the store's ingest door.
    """

    def __init__(
        self,
        *,
        max_entries: int = DEFAULT_MAX_CACHE_ENTRIES,
        idle_ttl_seconds: float = DEFAULT_IDLE_TTL_SECONDS,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_entries < 1:
            raise ValueError("EditSessionCache max_entries must be >= 1.")
        self.max_entries = max_entries
        self.idle_ttl_seconds = idle_ttl_seconds
        self._now = now
        # session_id -> (last_access_monotonic, state)
        self._entries: "OrderedDict[str, tuple[float, TwoStepSessionState]]" = OrderedDict()

    def evict_idle(self, now: float | None = None) -> list[str]:
        now = self._now() if now is None else now
        evicted: list[str] = []
        for session_id in list(self._entries):
            last_access, _state = self._entries[session_id]
            if now - last_access > self.idle_ttl_seconds:
                self._entries.pop(session_id, None)
                evicted.append(session_id)
        return evicted

    def get(self, session_id: str) -> TwoStepSessionState | None:
        self.evict_idle()
        entry = self._entries.get(session_id)
        if entry is None:
            return None
        # Touch: move to most-recently-used end.
        self._entries.pop(session_id, None)
        self._entries[session_id] = (self._now(), entry[1])
        return entry[1]

    def put(self, session_id: str, state: TwoStepSessionState) -> None:
        self.evict_idle()
        self._entries.pop(session_id, None)
        self._entries[session_id] = (self._now(), state)
        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)  # drop least-recently-used

    def remove(self, session_id: str) -> None:
        self._entries.pop(session_id, None)

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, session_id: str) -> bool:
        return session_id in self._entries


# ── Canonical Δ replay ───────────────────────────────────────────────────────
#
# The retained workflow revision is never persisted as an in-memory dict of
# record: it is re-derived by replaying the accepted canonical Δ ops over the
# session's base graph.  ``set_node_field`` sets a widget field by (node_uid,
# field_path); ``add_node`` appends a node; ``remove_node`` drops a node by id.


def _apply_delta_ops(base_graph: Mapping[str, Any] | None, ops: Any) -> dict[str, Any] | None:
    if not isinstance(base_graph, Mapping):
        return None
    from vibecomfy.ingest.normalize import door_setdefault_nodes  # Law 5 door

    graph: dict[str, Any] = json.loads(json.dumps(dict(base_graph)))
    nodes = door_setdefault_nodes(graph, [])
    if not isinstance(nodes, list):
        return graph
    for op in ops or ():
        if not isinstance(op, Mapping):
            continue
        kind = op.get("op")
        if kind == "set_node_field":
            target = op.get("target")
            if isinstance(target, (list, tuple)) and len(target) >= 3:
                _set_node_field(nodes, target[1], target[2], op.get("value"))
        elif kind == "set_mode":
            target = op.get("target")
            if isinstance(target, (list, tuple)) and len(target) >= 2:
                _set_node_mode(nodes, target[1], op.get("mode"))
        elif kind == "add_node":
            _add_node(nodes, op)
        elif kind == "remove_node":
            target = op.get("target")
            if isinstance(target, (list, tuple)) and len(target) >= 2:
                uid = target[1]
                nodes[:] = [
                    n for n in nodes
                    if not (isinstance(n, Mapping) and str(n.get("id")) == str(uid))
                ]
        elif kind == "upsert_link":
            _upsert_link(graph, nodes, op)
        elif kind == "remove_link":
            _remove_link(graph, nodes, op)
        elif kind == "subgraph_interface":
            _subgraph_interface(graph, op)
    return graph


def _node_by_uid(nodes: list[Any], uid: Any) -> tuple[int, dict[str, Any]] | None:
    for index, node in enumerate(nodes):
        if isinstance(node, dict) and str(node.get("id")) == str(uid):
            return index, node
    return None


def _set_node_field(nodes: list[Any], uid: Any, field_path: Any, value: Any) -> None:
    found = _node_by_uid(nodes, uid)
    if found is None:
        return
    _index, node = found
    field = str(field_path)
    if field in ("class_type", "type"):
        node["type"] = value
        node["class_type"] = value
        return
    node[field] = value


def _set_node_mode(nodes: list[Any], uid: Any, mode: Any) -> None:
    found = _node_by_uid(nodes, uid)
    if found is None:
        return
    _index, node = found
    node["mode"] = mode


def _add_node(nodes: list[Any], op: Mapping[str, Any]) -> None:
    # Canonical add_node: {scope_path, uid, node_id, class_type, fields, inputs}
    # Legacy add_node: {uid, fields}
    uid = op.get("uid")
    if uid is None:
        return
    fields = op.get("fields") if isinstance(op.get("fields"), Mapping) else {}
    node: dict[str, Any] = {"id": uid, **{k: v for k, v in fields.items() if k != "id"}}
    if op.get("class_type"):
        node["type"] = op["class_type"]
        node["class_type"] = op["class_type"]
    nodes.append(node)


def _input_slot_index(node: dict[str, Any], input_field: Any) -> int | None:
    inputs = node.get("inputs")
    if isinstance(inputs, list):
        for index, entry in enumerate(inputs):
            if isinstance(entry, dict) and str(entry.get("name")) == str(input_field):
                return index
        if str(input_field).isdigit():
            return int(input_field)
    return None


def _output_slot_index(node: dict[str, Any], output_slot: Any) -> int | None:
    outputs = node.get("outputs")
    if isinstance(outputs, list):
        for index, entry in enumerate(outputs):
            if isinstance(entry, dict) and str(entry.get("name")) == str(output_slot):
                return index
        if isinstance(output_slot, int):
            return output_slot
    return 0


def _link_type_for(node: dict[str, Any], output_slot: Any) -> str:
    outputs = node.get("outputs")
    if isinstance(outputs, list):
        for index, entry in enumerate(outputs):
            if isinstance(entry, dict) and str(entry.get("name")) == str(output_slot):
                return str(entry.get("type") or "*")
    return "*"


def _next_link_id(graph: dict[str, Any]) -> int:
    links = graph.get("links")
    max_id = 0
    if isinstance(links, list):
        for link in links:
            if isinstance(link, (list, tuple)) and link and isinstance(link[0], int):
                max_id = max(max_id, link[0])
            elif isinstance(link, Mapping) and isinstance(link.get("id"), int):
                max_id = max(max_id, link["id"])
    return max_id + 1


def _upsert_link(graph: dict[str, Any], nodes: list[Any], op: Mapping[str, Any]) -> None:
    source = op.get("from")
    target = op.get("to")
    if not (isinstance(source, (list, tuple)) and len(source) >= 3):
        return
    if not (isinstance(target, (list, tuple)) and len(target) >= 3):
        return
    suid, sslot, tuid, tfield = source[1], source[2], target[1], target[2]
    src = _node_by_uid(nodes, suid)
    dst = _node_by_uid(nodes, tuid)
    if src is None or dst is None:
        return
    _src_index, src_node = src
    _dst_index, dst_node = dst
    to_slot = _input_slot_index(dst_node, tfield)
    if to_slot is None:
        to_slot = 0
    from_slot = _output_slot_index(src_node, sslot)
    link_type = _link_type_for(src_node, sslot)
    links = graph.setdefault("links", [])
    if not isinstance(links, list):
        links = []
        graph["links"] = links
    # Remove any existing link terminating at (tuid, to_slot).
    removed_ids: set[int] = set()
    kept: list[Any] = []
    for link in links:
        if isinstance(link, (list, tuple)) and len(link) >= 5:
            if str(link[3]) == str(tuid) and link[4] == to_slot:
                removed_ids.add(link[0])
                continue
        elif isinstance(link, Mapping):
            if str(link.get("to_node", link.get("to"))) == str(tuid) and (
                link.get("to_slot", link.get("to_input")) == to_slot
            ):
                if isinstance(link.get("id"), int):
                    removed_ids.add(link["id"])
                continue
        kept.append(link)
    new_id = _next_link_id(graph)
    kept.append([new_id, suid, from_slot, tuid, to_slot, link_type])
    graph["links"] = kept
    # Patch the target node's input link reference.
    inputs = dst_node.get("inputs")
    if isinstance(inputs, list) and 0 <= to_slot < len(inputs):
        entry = inputs[to_slot]
        if isinstance(entry, dict):
            entry["link"] = new_id
    # Patch the source node's output link reference.
    outputs = src_node.get("outputs")
    if isinstance(outputs, list):
        for entry in outputs:
            if isinstance(entry, dict):
                refs = entry.get("links")
                if isinstance(refs, list):
                    refs[:] = [r for r in refs if r not in removed_ids]
                    if new_id not in refs:
                        refs.append(new_id)


def _remove_link(graph: dict[str, Any], nodes: list[Any], op: Mapping[str, Any]) -> None:
    links = graph.get("links")
    if not isinstance(links, list):
        return
    remove_id = op.get("id")
    to = op.get("to")
    tuid = tfield = None
    if isinstance(to, (list, tuple)) and len(to) >= 3:
        tuid, tfield = to[1], to[2]
    removed_ids: set[int] = set()
    kept: list[Any] = []
    for link in links:
        drop = False
        if isinstance(link, (list, tuple)) and len(link) >= 5:
            if remove_id is not None and link[0] == remove_id:
                drop = True
            elif tuid is not None and str(link[3]) == str(tuid) and _input_slot_index(
                _node_by_uid(nodes, tuid)[1] if _node_by_uid(nodes, tuid) else {}, tfield
            ) == link[4]:
                drop = True
            if drop:
                removed_ids.add(link[0])
        elif isinstance(link, Mapping):
            if remove_id is not None and link.get("id") == remove_id:
                drop = True
            elif tuid is not None and str(link.get("to_node", link.get("to"))) == str(tuid):
                drop = True
            if drop and isinstance(link.get("id"), int):
                removed_ids.add(link["id"])
        if not drop:
            kept.append(link)
    graph["links"] = kept
    for node in nodes:
        if not isinstance(node, dict):
            continue
        for entry in (node.get("inputs") or ()):
            if isinstance(entry, dict) and entry.get("link") in removed_ids:
                entry.pop("link", None)
        for entry in (node.get("outputs") or ()):
            if isinstance(entry, dict) and isinstance(entry.get("links"), list):
                entry["links"] = [r for r in entry["links"] if r not in removed_ids]


def _subgraph_interface(graph: dict[str, Any], op: Mapping[str, Any]) -> None:
    action = op.get("action")
    name = op.get("name")
    definitions = graph.setdefault("definitions", {})
    if not isinstance(definitions, dict):
        definitions = {}
        graph["definitions"] = definitions
    subgraphs = definitions.setdefault("subgraphs", [])
    if not isinstance(subgraphs, list):
        subgraphs = []
        definitions["subgraphs"] = subgraphs
    identity = op.get("id") or name
    if action == "add":
        subgraphs.append(
            {
                "name": name,
                "inputs": [list(p) for p in (op.get("inputs") or ())],
                "outputs": [list(p) for p in (op.get("outputs") or ())],
            }
        )
    elif action == "remove":
        subgraphs[:] = [
            s for s in subgraphs
            if not (isinstance(s, Mapping) and (s.get("name") == name or s.get("id") == identity))
        ]
    elif action == "change":
        for sub in subgraphs:
            if isinstance(sub, Mapping) and (sub.get("name") == name or sub.get("id") == identity):
                if op.get("inputs") is not None:
                    sub["inputs"] = [list(p) for p in op.get("inputs")]
                if op.get("outputs") is not None:
                    sub["outputs"] = [list(p) for p in op.get("outputs")]


def serialize_delta_ops(landed_ops: Any) -> tuple[dict[str, Any], ...]:
    """Serialize landed typed edit ops to canonical dicts for the Δ ledger.

    The canonical dict form is produced by
    :func:`vibecomfy.porting.edit.ops.canonical_op_to_dict` — the same shape
    :func:`_apply_delta_ops` replays — so restart reconstruction and the live
    apply path share ONE interpreter contract for every operation kind.
    """
    from vibecomfy.porting.edit.ops import canonical_op_to_dict  # noqa: PLC0415

    serialized: list[dict[str, Any]] = []
    for op in landed_ops or ():
        if isinstance(op, Mapping):
            serialized.append(dict(op))
            continue
        try:
            serialized.append(canonical_op_to_dict(op))
        except Exception:  # noqa: BLE001 - best-effort serialization
            continue
    return tuple(serialized)


def canonical_workflow_hash(graph: Any) -> str | None:
    """Stable hash for the retained revision (used for stale-message CAS)."""
    if graph is None:
        return None
    import hashlib

    raw = json.dumps(graph, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


# ── The durable store ────────────────────────────────────────────────────────


class TwoStepSessionStore:
    """Durable append-only transcript + rehydratable in-process cache.

    ``session_root`` defaults to the existing durable session directory
    (``out/editor_sessions``).  All transcript mutations are serialized with the
    process-safe :class:`SessionStateLock` (reused, never recreated) and write
    one JSON line per event under ``<session_dir>/two_step_execute.jsonl``.
    """

    def __init__(
        self,
        session_root: Path | str = DEFAULT_TWO_STEP_SESSION_ROOT,
        *,
        idle_ttl_seconds: float = DEFAULT_IDLE_TTL_SECONDS,
        max_cache_entries: int = DEFAULT_MAX_CACHE_ENTRIES,
        lock_timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
        now: Callable[[], float] = time.monotonic,
        now_iso: Callable[[], str] = _now_iso,
    ) -> None:
        self.session_root = Path(session_root)
        self.cache = EditSessionCache(
            max_entries=max_cache_entries,
            idle_ttl_seconds=idle_ttl_seconds,
            now=now,
        )
        self.lock_timeout_seconds = lock_timeout_seconds
        self._now = now
        self._now_iso = now_iso

    # -- paths ---------------------------------------------------------------

    def session_dir(self, session_id: str) -> Path:
        return session_dir_for(self.session_root, normalize_session_id(session_id))

    def transcript_path(self, session_id: str) -> Path:
        return self.session_dir(session_id) / TWO_STEP_TRANSCRIPT_NAME

    def base_graph_path(self, session_id: str) -> Path:
        return self.session_dir(session_id) / TWO_STEP_BASE_GRAPH_NAME

    def workflow_path(self, session_id: str) -> Path:
        return self.session_dir(session_id) / TWO_STEP_WORKFLOW_NAME

    # -- load / ingest -------------------------------------------------------

    def load(self, session_id: str) -> TwoStepSessionState | None:
        """Return the cached view, else rehydrate from the durable transcript.

        Returns ``None`` when no transcript exists (the caller decides whether
        to open a fresh session — a missing id is NEVER silently created here).
        """
        safe_id = normalize_session_id(session_id)
        cached = self.cache.get(safe_id)
        if cached is not None:
            return cached
        state = self.ingest_transcript(safe_id)
        if state is not None:
            self.cache.put(safe_id, state)
        return state

    def exists(self, session_id: str) -> bool:
        return self.transcript_path(session_id).is_file()

    def ingest_transcript(self, session_id: str) -> TwoStepSessionState | None:
        """Named ingest door: rebuild the state view from the JSONL transcript.

        The transcript is the single source of truth.  If it is absent, the
        session has no durable record and this returns ``None``.
        """
        safe_id = normalize_session_id(session_id)
        path = self.transcript_path(safe_id)
        if not path.is_file():
            return None
        state = fresh_state(safe_id, now_iso="")
        events: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    LOGGER.warning("two-step transcript: skipping corrupt line in %s", path)
                    continue
                if isinstance(event, dict):
                    events.append(event)
        state = self._fold_events(state, events)
        if not state.created_at and events:
            first = events[0]
            state = replace(state, created_at=str(first.get("ts") or ""))
        state = replace(state, updated_at=str(events[-1].get("ts") or "") if events else "")
        return state

    def replay_workflow(
        self, state: TwoStepSessionState, *, base_graph: Mapping[str, Any] | None = None
    ) -> dict[str, Any] | None:
        """Canonical Δ replay: re-derive the retained revision from the base
        graph plus the session's accepted Δ ops (in acceptance order)."""
        if base_graph is None:
            base_graph = self._read_base_graph(state.session_id)
        graph = base_graph
        for ref in state.accepted_delta_refs:
            graph = _apply_delta_ops(graph, ref.get("ops"))
        return graph

    def retained_workflow(self, session_id: str) -> dict[str, Any] | None:
        """Return the retained revision, preferring the sidecar then replay."""
        state = self.load(session_id)
        if state is None:
            return None
        sidecar = self.workflow_path(session_id)
        if sidecar.is_file():
            try:
                return json.loads(sidecar.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
        return self.replay_workflow(state)

    def write_workflow(self, session_id: str, graph: Mapping[str, Any]) -> None:
        """Persist the retained revision sidecar (durable candidate graph).

        Written under the reused process-safe lock so a concurrent reader never
        observes a half-written revision.  Replay stays the authority when the
        sidecar is absent; this is the durable candidate the execute phase
        returns after an accepted edit.
        """
        safe_id = normalize_session_id(session_id)
        session_dir = self.session_dir(safe_id)
        with SessionStateLock(session_dir, timeout_seconds=self.lock_timeout_seconds):
            session_dir.mkdir(parents=True, exist_ok=True)
            self.workflow_path(safe_id).write_text(
                json.dumps(dict(graph), sort_keys=True, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

    # -- mutation ------------------------------------------------------------

    def append(
        self,
        session_id: str,
        kind: str,
        payload: Mapping[str, Any] | None = None,
        *,
        turn: int | None = None,
    ) -> TwoStepSessionState:
        """Serialize and append one transcript event; return the new state view.

        Uses the reused process-safe :class:`SessionStateLock`; a concurrent
        writer (same session) blocks until the lock is free, so the transcript
        stays append-only and ordered.
        """
        return self.append_events(session_id, [{"kind": kind, "turn": turn, **(dict(payload or {}))}])

    def append_events(self, session_id: str, events: list[dict[str, Any]]) -> TwoStepSessionState:
        safe_id = normalize_session_id(session_id)
        session_dir = self.session_dir(safe_id)
        with SessionStateLock(session_dir, timeout_seconds=self.lock_timeout_seconds):
            session_dir.mkdir(parents=True, exist_ok=True)
            path = self.transcript_path(safe_id)
            existing = self.ingest_transcript(safe_id)
            state = existing if existing is not None else fresh_state(safe_id)
            next_seq = self._next_seq(state, path)
            ts = self._now_iso()
            with path.open("a", encoding="utf-8") as handle:
                for event in events:
                    record: dict[str, Any] = {"seq": next_seq, "ts": ts, "kind": event.get("kind")}
                    if event.get("turn") is not None:
                        record["turn"] = int(event["turn"])
                    record.update({k: v for k, v in event.items() if k not in ("kind", "turn")})
                    handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
                    state = self._fold_event(state, record)
                    next_seq += 1
            state = replace(state, updated_at=ts)
            self.cache.put(safe_id, state)
            return state

    # -- open / close / begin-turn ------------------------------------------

    def open_session(
        self, session_id: str, *, base_graph: Mapping[str, Any] | None = None
    ) -> TwoStepSessionState:
        """Open (or reload) a session.  Never mints a fresh session for an id
        whose durable transcript exists but is closed (callers must check)."""
        safe_id = normalize_session_id(session_id)
        existing = self.load(safe_id)
        if existing is not None:
            if existing.closed:
                raise TwoStepSessionError(
                    ERROR_SESSION_EXPIRED,
                    f"session {safe_id!r} is closed/expired.",
                    session_id=safe_id,
                )
            return existing
        state = fresh_state(safe_id)
        if base_graph is not None:
            self._write_base_graph(safe_id, base_graph)
            state = replace(state, last_workflow_hash=canonical_workflow_hash(base_graph))
        self.cache.put(safe_id, state)
        return state

    def close(self, session_id: str) -> TwoStepSessionState:
        """Close a session; subsequent messages raise ``session_expired``."""
        return self.append(session_id, "closed", {"closed": True})

    def begin_message(
        self,
        session_id: str | None,
        *,
        base_graph: Mapping[str, Any] | None = None,
        expected_baseline_hash: str | None = None,
        message_fingerprint: str | None = None,
        lease_token: str | None = None,
    ) -> TwoStepSessionState:
        """Validate identity + staleness/concurrency BEFORE any model work.

        * Missing ``session_id`` → ``invalid_request``.
        * Closed session → ``session_expired`` (never a fresh session).
        * ``expected_baseline_hash`` that disagrees with the retained revision
          → ``stale_message``.
        * ``message_fingerprint`` (or *lease_token*) already in flight →
          ``concurrent_message``.

        Every message — with or without an idempotency key — acquires a durable
        whole-turn lease (keyed by ``message_fingerprint`` when present, else a
        fresh :func:`mint_lease_token`).  Leases from different fingerprints
        coexist (a second, distinct message is NOT lost), while a replay of the
        SAME key is refused so tools/edits are never duplicated.
        """
        if not session_id:
            raise TwoStepSessionError(
                ERROR_INVALID_REQUEST,
                "two-step execute requires a session_id (the server never mints ids).",
            )
        safe_id = normalize_session_id(session_id)
        lease_key = lease_token or message_fingerprint or mint_lease_token()
        session_dir = self.session_dir(safe_id)
        with SessionStateLock(session_dir, timeout_seconds=self.lock_timeout_seconds):
            existing = self.load(safe_id)
            if existing is not None and existing.closed:
                raise TwoStepSessionError(
                    ERROR_SESSION_EXPIRED,
                    f"session {safe_id!r} is closed/expired.",
                    session_id=safe_id,
                )
            # Stale detection against the retained revision (CAS precursor).
            if expected_baseline_hash and existing is not None and existing.last_workflow_hash:
                if expected_baseline_hash != existing.last_workflow_hash:
                    raise TwoStepSessionError(
                        ERROR_STALE_MESSAGE,
                        "message baseline does not match the retained workflow revision.",
                        session_id=safe_id,
                        detail={
                            "expected": expected_baseline_hash,
                            "retained": existing.last_workflow_hash,
                        },
                    )
            marker = self._read_in_flight(safe_id)
            if lease_key in marker:
                raise TwoStepSessionError(
                    ERROR_CONCURRENT_MESSAGE,
                    "a message for this session is already in flight.",
                    session_id=safe_id,
                    detail={"fingerprint": lease_key},
                )
            self._acquire_in_flight(safe_id, lease_key)
            state = self.open_session(safe_id, base_graph=base_graph)
            return state

    def end_message(
        self,
        session_id: str,
        *,
        message_fingerprint: str | None = None,
        lease_token: str | None = None,
    ) -> None:
        """Release the in-flight lease set by :meth:`begin_message`.

        Only the lease this turn acquired is released — a distinct message's
        lease (and a replay-refused lease) is never cleared.  Pass
        *lease_token* for anonymous (no-idempotency-key) turns.
        """
        key = lease_token or message_fingerprint
        if not session_id or not key:
            return
        safe_id = normalize_session_id(session_id)
        session_dir = self.session_dir(safe_id)
        with SessionStateLock(session_dir, timeout_seconds=self.lock_timeout_seconds):
            self._release_in_flight(safe_id, key)

    # -- internal ------------------------------------------------------------

    def _in_flight_path(self, session_id: str) -> Path:
        return self.session_dir(session_id) / TWO_STEP_IN_FLIGHT_NAME

    def _read_in_flight(self, session_id: str) -> dict[str, Any]:
        path = self._in_flight_path(session_id)
        if not path.is_file():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _acquire_in_flight(self, session_id: str, lease_key: str) -> None:
        marker = self._read_in_flight(session_id)
        marker[lease_key] = {"ts": self._now()}
        self.session_dir(session_id).mkdir(parents=True, exist_ok=True)
        self._in_flight_path(session_id).write_text(
            json.dumps(marker, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _release_in_flight(self, session_id: str, lease_key: str) -> None:
        marker = self._read_in_flight(session_id)
        marker.pop(lease_key, None)
        path = self._in_flight_path(session_id)
        if marker:
            path.write_text(json.dumps(marker, sort_keys=True) + "\n", encoding="utf-8")
        else:
            path.unlink(missing_ok=True)

    # -- completed fingerprint → outcome (idempotent retry) ------------------

    def outcomes_path(self, session_id: str) -> Path:
        return self.session_dir(session_id) / TWO_STEP_OUTCOMES_NAME

    def record_completed(
        self,
        session_id: str,
        fingerprint: str,
        outcome: Mapping[str, Any],
    ) -> None:
        """Persist a completed fingerprint → outcome record.

        A later retry of the SAME fingerprint returns the stored outcome instead
        of re-running tools/edits (idempotent replay).
        """
        if not fingerprint:
            return
        safe_id = normalize_session_id(session_id)
        session_dir = self.session_dir(safe_id)
        with SessionStateLock(session_dir, timeout_seconds=self.lock_timeout_seconds):
            session_dir.mkdir(parents=True, exist_ok=True)
            record = {
                "fingerprint": fingerprint,
                "ts": self._now_iso(),
                "outcome": _jsonish(outcome),
            }
            with self.outcomes_path(safe_id).open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")

    def completed_outcome(
        self, session_id: str, fingerprint: str
    ) -> dict[str, Any] | None:
        """Return the most recent completed outcome for *fingerprint*, if any."""
        if not fingerprint:
            return None
        path = self.outcomes_path(session_id)
        if not path.is_file():
            return None
        found: dict[str, Any] | None = None
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(record, Mapping) and record.get("fingerprint") == fingerprint:
                        outcome = record.get("outcome")
                        found = outcome if isinstance(outcome, Mapping) else None
        except OSError:
            return None
        return dict(found) if found is not None else None

    def _read_base_graph(self, session_id: str) -> dict[str, Any] | None:
        path = self.base_graph_path(session_id)
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _write_base_graph(self, session_id: str, base_graph: Mapping[str, Any]) -> None:
        session_dir = self.session_dir(session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        self.base_graph_path(session_id).write_text(
            json.dumps(dict(base_graph), sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def _next_seq(self, state: TwoStepSessionState, path: Path) -> int:
        # The seq is derived from the transcript itself (count lines), not from
        # in-memory state, so a restarted process never reuses a sequence.
        if not path.is_file():
            return 1
        count = 0
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    count += 1
        return count + 1

    def _fold_event(self, state: TwoStepSessionState, event: Mapping[str, Any]) -> TwoStepSessionState:
        kind = event.get("kind")
        turn = int(event.get("turn") or 0)
        route = event.get("route")

        if kind == "route":
            state = replace(
                state,
                route_history=state.route_history + ({"route": route, "turn": turn, "at": event.get("ts") or _now_iso()},),
            )
        elif kind == "user_message":
            query = str(event.get("query") or "")
            state = replace(
                state,
                messages=state.messages + ({"turn": turn, "role": "user", "content": query, "route": route},),
                budget=state.budget.record_user_message(),
            )
        elif kind == "tool_call":
            state = replace(
                state,
                evidence_ledger=state.evidence_ledger + (
                    {
                        "turn": turn,
                        "tool": event.get("tool"),
                        "evidence_ids": list(event.get("evidence_ids") or ()),
                        "digest": str(event.get("digest") or ""),
                    },
                ),
                messages=state.messages + (
                    {"turn": turn, "role": "assistant_tool", "content": str(event.get("digest") or ""), "route": route},
                ),
            )
        elif kind == "delta_accepted":
            state = replace(
                state,
                accepted_delta_refs=state.accepted_delta_refs + (
                    {
                        "turn": turn,
                        "delta_ids": list(event.get("delta_ids") or ()),
                        "ops": list(event.get("ops") or ()),
                    },
                ),
                last_workflow_hash=event.get("workflow_hash") or state.last_workflow_hash,
            )
        elif kind == "lens_fact":
            state = replace(
                state,
                lens_facts=state.lens_facts + (
                    {"turn": turn, "fact_ids": list(event.get("fact_ids") or ()), "route": route},
                ),
            )
        elif kind == "reply":
            reply_text = str(event.get("reply") or "")
            state = replace(
                state,
                replies=state.replies + ({"turn": turn, "reply": reply_text, "at": event.get("ts") or _now_iso()},),
                messages=state.messages + ({"turn": turn, "role": "assistant_reply", "content": reply_text, "route": route},),
            )
        elif kind == "apply_accepted":
            ids = list(event.get("delta_ids") or ())
            text = f"edit accepted: delta_ids={ids}"
            state = replace(
                state,
                messages=state.messages + ({"turn": turn, "role": "assistant_edit", "content": text, "route": route},),
            )
        elif kind == "apply_rejected":
            diagnostics = " | ".join(str(d) for d in (event.get("diagnostics") or ()))
            text = f"edit rejected: {event.get('reason') or 'rejected'}" + (
                f" — {diagnostics}" if diagnostics else ""
            )
            if event.get("replacement_allowed"):
                text += " (one replacement allowed)"
            if event.get("no_candidate"):
                text += " (no candidate — do not submit another edit)"
            state = replace(
                state,
                messages=state.messages + ({"turn": turn, "role": "assistant_feedback", "content": text, "route": route},),
            )
        elif kind == "budget":
            state = replace(state, budget=SessionBudget.from_dict(event.get("budget") or {}))
        elif kind == "closed":
            state = replace(state, closed=True)
        return state

    def _fold_events(self, state: TwoStepSessionState, events: list[dict[str, Any]]) -> TwoStepSessionState:
        for event in events:
            state = self._fold_event(state, event)
        return state


__all__ = [
    "DEFAULT_IDLE_TTL_SECONDS",
    "DEFAULT_MAX_CACHE_ENTRIES",
    "DEFAULT_TWO_STEP_SESSION_ROOT",
    "ERROR_CONCURRENT_MESSAGE",
    "ERROR_INVALID_REQUEST",
    "ERROR_MISSING_DELTA_REFERENCE",
    "ERROR_SESSION_EXPIRED",
    "ERROR_STALE_MESSAGE",
    "EditSessionCache",
    "SessionBudget",
    "TwoStepSessionError",
    "TwoStepSessionState",
    "TwoStepSessionStore",
    "canonical_workflow_hash",
    "derive_research_attempt",
    "fresh_state",
    "mint_lease_token",
    "normalize_session_id",
    "serialize_delta_ops",
]
