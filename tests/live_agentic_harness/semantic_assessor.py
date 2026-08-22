"""T5.2 canonical semantic assessor.

The assessor consumes TYPED carriers — ingest-door views, ``WorkflowSnapshot``
graphs, closed checkpoints/projections — never arbitrary graph dictionaries.
Every carrier passes through ONE constructor that detects the wire shape and
decodes it through its own named ingest door (``from_envelope`` / ``from_ui`` /
``from_api``), tagging the source representation. A mixed pair (UI original +
API final, the r5 failure) is therefore decoded correctly per side instead of
being forced through one decoder.

Verdict law (plan §T5.2 + contract 11):

* A graph pair requires matching lineage; a mismatch is rejected outright.
* With unchanged products or no accepted delta/candidate, NO edit is ever
  synthesized (no diff-seeding): an unchanged product is determined ``no_edit``
  evidence, never a pass.
* Missing or contradictory evidence is ``undetermined`` — never an empty
  graph, a fabricated removal, or a guessed green.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from vibecomfy.comfy_nodes.agent.artifact_lineage import (
    canonical_lineage_digest,
)

__all__ = [
    "CanonicalSemanticView",
    "LineageMismatch",
    "PairVerdict",
    "TypedCarrierRequired",
    "canonical_semantic_view",
    "judge_graph_pair",
    "load_accepted_batch_ops",
    "require_matching_lineage",
]


class TypedCarrierRequired(ValueError):
    """A payload is neither a typed carrier nor decodable through a named door."""


class LineageMismatch(ValueError):
    """A graph pair's carriers disagree on scenario/session/turn/baseline."""


@dataclass(frozen=True)
class CanonicalSemanticView:
    """One shape-aware, digest-tagged semantic view of a graph."""

    source_representation: str  # "snapshot" | "envelope" | "ui" | "api"
    workflow: Any               # retained VibeWorkflow IR
    content_digest: str         # SHA-256 over canonical raw content
    lineage: dict[str, str] = field(default_factory=dict)


def canonical_semantic_view(
    payload: Any,
    *,
    lineage: Mapping[str, Any] | None = None,
    schema_provider: Any = None,
    use_comfy_converter: bool | None = None,
) -> CanonicalSemanticView:
    """Construct one typed semantic view through the common constructor.

    Accepts, exhaustively:

    * a ``WorkflowSnapshot`` (T1.1 typed carrier) — used as-is;
    * an object exposing ``workflow`` + ``source_representation`` +
      ``semantic_digest`` (checkpoint/graph carriers);
    * a raw UI/API/envelope mapping — decoded through exactly ONE named
      ingest door chosen by shape, never by guessing.

    Anything else raises :class:`TypedCarrierRequired`; decoding failures
    propagate (fail-closed), they are never swallowed into an empty graph.
    """
    frozen_lineage = {
        str(k): str(v or "")
        for k, v in (lineage or {}).items()
    }

    # Typed carrier 1: the immutable ingest snapshot itself.
    if type(payload).__name__ == "WorkflowSnapshot" and hasattr(payload, "workflow"):
        snap_lineage = getattr(payload, "lineage", None)
        merged = dict(frozen_lineage)
        for key in ("scenario_id", "session_id", "turn_id", "baseline_id"):
            value = getattr(snap_lineage, key, None)
            if value and not merged.get(key):
                merged[key] = str(value)
        return CanonicalSemanticView(
            source_representation=str(
                getattr(payload, "source_representation", "") or "snapshot"
            ),
            workflow=payload.workflow,
            content_digest=str(getattr(payload, "source_digest", "") or ""),
            lineage=merged,
        )


    # Typed carrier 2: any graph-bearing carrier object (checkpoints,
    # projections) exposing the snapshot field triple.
    if hasattr(payload, "workflow") and hasattr(payload, "source_representation"):
        return CanonicalSemanticView(
            source_representation=str(getattr(payload, "source_representation") or "carrier"),
            workflow=getattr(payload, "workflow"),
            content_digest=str(getattr(payload, "semantic_digest", "") or ""),
            lineage=dict(frozen_lineage),
        )

    if isinstance(payload, Mapping):
        raw = dict(payload)
        digest = canonical_lineage_digest(raw)
        from vibecomfy.ingest.normalize import (
            _is_vibe_envelope,
            from_api,
            from_envelope,
            from_ui,
        )

        if _is_vibe_envelope(raw):
            workflow = from_envelope(raw)
            representation = "envelope"
        elif isinstance(raw.get("nodes"), list):
            workflow = from_ui(
                raw,
                schema_provider=schema_provider,
                use_comfy_converter=(
                    _comfy_available() if use_comfy_converter is None else use_comfy_converter
                ),
            )
            representation = "ui"
        elif not raw.get("nodes") and raw and all(
            isinstance(v, Mapping) and "class_type" in v for v in raw.values()
        ):
            # ComfyUI prompt/API format: flat {uid: {class_type, inputs, ...}}.
            workflow = from_api(
                raw,
                schema_provider=schema_provider,
            )
            representation = "api"
        else:
            raise TypedCarrierRequired(
                "payload matches no named ingest door "
                "(envelope|ui|api); refusing to guess a decode"
            )
        return CanonicalSemanticView(
            source_representation=representation,
            workflow=workflow,
            content_digest=digest,
            lineage=dict(frozen_lineage),
        )

    raise TypedCarrierRequired(
        f"unsupported assessor carrier type: {type(payload).__name__}"
    )


def _comfy_available() -> bool:
    """Whether the optional ComfyUI converter runtime is importable."""
    try:
        import comfy  # noqa: F401
    except Exception:  # noqa: BLE001 - headless harness has no ComfyUI runtime
        return False
    return True


_LINEAGE_KEYS = ("scenario_id", "session_id", "turn_id", "baseline_id")


def require_matching_lineage(
    pre: CanonicalSemanticView,
    post: CanonicalSemanticView,
) -> None:
    """Refuse pairs whose carriers disagree on shared lineage identity.

    Empty strings are "unknown at this carrier"; two known values for the
    same key must agree, otherwise the pair is stale-path/cross-turn evidence.
    """
    for key in _LINEAGE_KEYS:
        left = pre.lineage.get(key, "")
        right = post.lineage.get(key, "")
        if left and right and left != right:
            raise LineageMismatch(
                f"graph pair lineage mismatch on {key}: {left!r} != {right!r}"
            )


@dataclass(frozen=True)
class PairVerdict:
    """Honest verdict over one graph pair under the accepted-delta authority."""

    outcome: str  # "applied_edit" | "no_edit" | "delta_replay_mismatch" | "undetermined"
    reason: str
    detail: dict[str, Any] = field(default_factory=dict)


def load_accepted_batch_ops(
    response: Mapping[str, Any] | None,
) -> tuple[tuple[Mapping[str, Any], ...], bool]:
    """Return ``(accepted_ops, queue_gate_failed)`` from a run response.

    Only ``accepted_batch`` is consulted (the sole durable edit authority);
    legacy ``delta_ops`` projections are ignored here by design.
    """
    queue_gate_failed = False
    if not isinstance(response, Mapping):
        return (), queue_gate_failed
    gates = response.get("gates")
    queue_gate_failed = isinstance(gates, Mapping) and gates.get("queue_validate_ok") is False
    accepted = response.get("accepted_batch")
    ops: tuple[Mapping[str, Any], ...] = ()
    if isinstance(accepted, (list, tuple)):
        ops = tuple(
            dict(item["op"])
            for item in accepted
            if isinstance(item, Mapping) and isinstance(item.get("op"), Mapping)
        )
    return ops, bool(queue_gate_failed)


def judge_graph_pair(
    pre: CanonicalSemanticView,
    post: CanonicalSemanticView,
    accepted_ops: tuple[Mapping[str, Any], ...],
    *,
    schema_provider: Any = None,
    queue_gate_failed: bool = False,
) -> PairVerdict:
    """Judge one lineage-matched pair WITHOUT ever synthesizing edits.

    * unchanged product + no accepted delta ⇒ ``no_edit`` (determined absence;
      the caller decides pass/fail against the scenario expectation);
    * changed product + no accepted delta ⇒ ``undetermined`` (contradictory:
      something changed without durable authority — C11 forbids guessing);
    * accepted delta present ⇒ replay ``interpret(pre, Δ)`` must reconstruct
      the post product; contradiction is ``delta_replay_mismatch`` (fail-closed),
      reconstruction success is ``applied_edit``.
    """
    require_matching_lineage(pre, post)
    if not accepted_ops:
        unchanged = pre.content_digest == post.content_digest
        if unchanged:
            return PairVerdict(
                outcome="no_edit",
                reason="no_accepted_delta_and_unchanged_product",
                detail={
                    "pre_digest": pre.content_digest,
                    "post_digest": post.content_digest,
                    "queue_gate_failed": queue_gate_failed,
                },
            )
        return PairVerdict(
            outcome="undetermined",
            reason="changed_product_without_accepted_delta",
            detail={
                "pre_digest": pre.content_digest,
                "post_digest": post.content_digest,
                "queue_gate_failed": queue_gate_failed,
            },
        )
    if queue_gate_failed:
        # A batch withheld from Apply authority cannot back a verdict; grading
        # against it would resurrect authority the gate refused.
        return PairVerdict(outcome="undetermined", reason="withheld_accepted_batch")

    from vibecomfy.porting.edit._diff import diff  # noqa: PLC0415
    from vibecomfy.porting.edit.ops import canonical_op_to_dict, parse_edit_delta  # noqa: PLC0415

    try:
        landed = parse_edit_delta([dict(op) for op in accepted_ops])
    except Exception as exc:  # noqa: BLE001 - malformed Δ cannot grade green
        return PairVerdict(
            outcome="undetermined",
            reason=f"unparseable_accepted_delta: {exc}",
        )
    derived = diff(pre.workflow, post.workflow, schema_provider=schema_provider)

    def _claim_set(ops):
        return {
            json.dumps(canonical_op_to_dict(op), sort_keys=True, default=str)
            for op in ops
        }

    claimed = _claim_set(landed)
    observed = _claim_set(derived)
    if claimed != observed:
        return PairVerdict(
            outcome="undetermined",
            reason="accepted_delta_does_not_reconstruct_post_product",
            detail={
                "claimed_only": sorted(claimed - observed)[:6],
                "observed_only": sorted(observed - claimed)[:6],
            },
        )
    return PairVerdict(outcome="applied_edit", reason="accepted_delta_matches_product")


def load_json_mapping(path: Path) -> Mapping[str, Any] | None:
    """Best-effort JSON mapping loader for artifact files."""
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return loaded if isinstance(loaded, Mapping) else None
