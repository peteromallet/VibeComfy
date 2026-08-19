"""RC-P5: replay fidelity — the accepted Δ must reconstruct the emitted graph.

The accepted Δ (``accepted_batch[*].op``) is the ONE authority for what an edit
changed (strategy-r7 §3).  Two replay consumers must agree on it:

1. The emit-door replay (``_apply_delta_ops``) — re-ingests the session base
   graph, applies the accepted ops copy-on-write, and re-emits UI.  Its output
   is the retained revision / final UI.
2. The judge's replay (``_verify_delta_replay``) — replays the accepted Δ over
   the pre-IR through the SAME emit door and checks it reconstructs post over
   the editable quotient.

RC-P5 regression coverage: every op kind round-trips through the real runtime,
the nine r8 "delta replay mismatch" scenarios reconstruct (quotient equality,
and the judge's replay check passes), replay is deterministic, and a multi-op
batch reconstructs every effect.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from vibecomfy.executor.two_step import _two_step_schema_provider
from vibecomfy.executor.two_step_session import _apply_delta_ops
from vibecomfy.porting.edit.apply_gate import editable_signature
from vibecomfy.porting.edit.session import EditSession
from vibecomfy.ingest.normalize import _assert_nonempty_ingest_preserved, _named_import
from vibecomfy.porting.edit.ops import canonical_op_to_dict

REPO_ROOT = Path(__file__).parents[1]
R8_ATTEMPTS = REPO_ROOT / "out/agentic/one-step-30-r8/attempts"
SESSION_ROOT = REPO_ROOT / "out/editor_sessions"

# The nine r8 scenarios whose judge rejected "delta replay mismatch".
R8_MISMATCH_SCENARIOS = (
    "3d-converts-image-to-3d-model",
    "3d-generates-a-3d-mesh-from",
    "audio-tts-narration-using-indextts-2",
    "image-animatediff-video-generation-with-vae-d20410",
    "image-image-editing-with-qwen-image",
    "image-style-transfer-using-ip-adapter",
    "image-two-stage-qwen-image-generation",
    "multi-3d-preview-and-image-output-workflow-d93baf",
    "multi-image-to-video-generation-with",
)


def _scenario_dir(scenario: str) -> Path:
    return R8_ATTEMPTS / scenario / "attempt_1" / scenario


def _session_id(scenario: str) -> str:
    resp = json.loads((_scenario_dir(scenario) / "response.json").read_text())
    return str(resp["session_id"])


def _accepted_ops(scenario: str) -> list[dict[str, Any]]:
    resp = json.loads((_scenario_dir(scenario) / "response.json").read_text())
    return [
        dict(item["op"])
        for item in (resp.get("accepted_batch") or ())
        if isinstance(item, dict) and isinstance(item.get("op"), dict)
    ]


def _base_graph(scenario: str) -> dict[str, Any]:
    return json.loads(
        (SESSION_ROOT / _session_id(scenario) / "two_step_base_graph.json").read_text()
    )


def _final_ui(scenario: str) -> dict[str, Any]:
    return json.loads((_scenario_dir(scenario) / "final.ui.json").read_text())


@pytest.fixture(scope="module")
def schema_provider() -> Any:
    return _two_step_schema_provider()


def _lift(ui: dict[str, Any], schema_provider: Any) -> Any:
    wf = _named_import(dict(ui), schema_provider=schema_provider, use_comfy_converter=False)
    _assert_nonempty_ingest_preserved(dict(ui), wf)
    return wf


def _replay(scenario: str, schema_provider: Any) -> dict[str, Any]:
    replayed = _apply_delta_ops(
        _base_graph(scenario), _accepted_ops(scenario), schema_provider=schema_provider
    )
    assert replayed is not None
    return replayed


# ── Test 2: the nine r8 mismatch scenarios reconstruct the emitted post ──────


@pytest.mark.parametrize("scenario", R8_MISMATCH_SCENARIOS)
def test_r8_scenario_replay_reconstructs_emitted_post_quotient(
    scenario: str, schema_provider: Any
) -> None:
    """replay(base, accepted ops) equals the emitted post over the editable quotient."""
    replayed = _replay(scenario, schema_provider)
    final = _final_ui(scenario)
    assert editable_signature(_lift(replayed, schema_provider)) == editable_signature(
        _lift(final, schema_provider)
    ), f"{scenario}: emit-door replay diverged from the emitted post quotient"


@pytest.mark.parametrize("scenario", R8_MISMATCH_SCENARIOS)
def test_r8_scenario_judge_replay_check_passes(scenario: str, schema_provider: Any) -> None:
    """The judge's replay check (same emit door) returns verified=True."""
    sys.path.insert(0, str(REPO_ROOT / "tests"))
    from live_agentic_harness.intent_judge import _verify_delta_replay  # noqa: PLC0415

    pre = json.loads((_scenario_dir(scenario) / "original.ui.json").read_text())
    post = _final_ui(scenario)
    verdict = _verify_delta_replay(
        pre, post, _accepted_ops(scenario), schema_provider=schema_provider
    )
    assert verdict.get("verified") is True, (
        f"{scenario}: judge replay check failed: {verdict.get('mismatches')}"
    )


# ── Test 3: replay determinism ───────────────────────────────────────────────


@pytest.mark.parametrize("scenario", R8_MISMATCH_SCENARIOS)
def test_replay_is_deterministic(scenario: str, schema_provider: Any) -> None:
    first = json.dumps(_replay(scenario, schema_provider), sort_keys=True, ensure_ascii=False)
    second = json.dumps(_replay(scenario, schema_provider), sort_keys=True, ensure_ascii=False)
    assert first == second


# ── Test 1 / 4: op-kind round-trips through the real runtime ─────────────────


def _mini_base() -> dict[str, Any]:
    return {
        "1": {"class_type": "LawNode", "inputs": {"widget_0": "a", "widget_1": 3, "widget_2": "x"}},
        "2": {"class_type": "LawNode", "inputs": {"src": ["1", 0], "widget_0": "b"}},
    }


def _ops(result: Any) -> list[dict[str, Any]]:
    return [canonical_op_to_dict(op) for op in result.landed_ops]


def _typed(ops: list[dict[str, Any]]) -> list[Any]:
    """Convert canonical op dicts to typed ops for :meth:`EditSession.apply_ops`."""
    from vibecomfy.porting.edit.ops import parse_edit_op

    return [parse_edit_op(op) for op in ops]


def test_set_node_field_roundtrip_reconstructs_live_emit(schema_provider: Any) -> None:
    session = EditSession(_mini_base(), schema_provider=schema_provider)
    ops = [
        {"op": "set_node_field", "target": ["", "1", "widget_1"], "value": 9},
    ]
    result = session.apply_ops(_typed(ops))
    assert result.ok and result.landed_ops
    live_ui = session.working_ui
    replayed = _apply_delta_ops(_mini_base(), _ops(result), schema_provider=schema_provider)
    assert replayed is not None
    assert editable_signature(_lift(replayed, schema_provider)) == editable_signature(
        _lift(live_ui, schema_provider)
    )


def test_add_node_roundtrip_reconstructs_live_emit(schema_provider: Any) -> None:
    session = EditSession(_mini_base(), schema_provider=schema_provider)
    ops = [
        {
            "op": "add_node",
            "scope_path": "",
            "uid": "n1",
            "node_id": "3",
            "class_type": "EmptyLatentImage",
            "fields": {"width": 512, "height": 512, "batch_size": 1},
            "inputs": {},
        },
    ]
    result = session.apply_ops(_typed(ops))
    assert result.ok and result.landed_ops
    live_ui = session.working_ui
    replayed = _apply_delta_ops(_mini_base(), _ops(result), schema_provider=schema_provider)
    assert replayed is not None
    assert editable_signature(_lift(replayed, schema_provider)) == editable_signature(
        _lift(live_ui, schema_provider)
    )


def test_multi_op_batch_reconstructs_both_effects(schema_provider: Any) -> None:
    session = EditSession(_mini_base(), schema_provider=schema_provider)
    ops = [
        {"op": "set_node_field", "target": ["", "1", "widget_1"], "value": 9},
        {"op": "set_node_field", "target": ["", "2", "widget_0"], "value": "z"},
    ]
    result = session.apply_ops(_typed(ops))
    assert result.ok and len(result.landed_ops) == 2
    live_ui = session.working_ui
    replayed = _apply_delta_ops(_mini_base(), _ops(result), schema_provider=schema_provider)
    assert replayed is not None
    assert replayed == live_ui
