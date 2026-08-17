"""B07 (Flash): two-step comparison harness contract tests.

Deterministic, model-call-free tests for the Flash-owned pieces of the paired
full/two-step comparison:

- manifest count/hash validation: the canonical 100-descriptor lane and the
  Pro ``two_step_50_manifest.json`` (validated when it lands; until then the
  canonical 100 shape is the anchor and the 50-manifest tests are skipped
  with an explicit "coming from Pro B07" marker).
- classification-lock completeness + route equality (full and two-step legs
  must run the IDENTICAL locked decision).
- paired-run completeness (every scenario has both a ``full`` and a
  ``two_step`` leg).
- comparison bookkeeping on synthetic summaries — NO model calls anywhere in
  this file.
- honest treatment of blocked provider/infra results: an infra-blocked leg
  makes the pair ``blocked`` and is never counted as a product pass/fail.
- second comparator selection from ``ledger_scenario_ids()``
  (``vibecomfy/intent/_ledger.py``) with valid labels only
  (``current`` → ``ir-everywhere-57-v3``; ``ir-everywhere-57`` is invalid).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

import pytest

from tests.live_agentic_harness.adapter import (
    _resolve_pipeline_mode,
    _two_step_session_id,
)
from tests.live_agentic_harness.ledger_selection import (
    INVALID_LEGACY_LEDGER_LABELS,
    LEDGER_ARTIFACT_LABEL,
    LEDGER_LABEL_CURRENT,
    LedgerLabelError,
    ledger_scenario_ids,
    ledger_selection_ids,
    resolve_ledger_label,
)
from tests.live_agentic_harness.runner import (
    _PIPELINE_MODE_ENV_VAR,
    _build_parser,
    _pinned_child_env,
    run_tag,
)
from tests.live_agentic_harness.scenario_manifest import (
    DEFAULT_MANIFEST_PATH,
    DEFAULT_SCENARIOS_DIR,
    discover_manifest_scenarios,
    write_manifest,
)
from vibecomfy.intent._ledger import LEDGER_ID_COUNT, assert_ledger_integrity

HARNESS_DIR = Path(__file__).parent / "live_agentic_harness"
TWO_STEP_50_MANIFEST = HARNESS_DIR / "two_step_50_manifest.json"
CLASSIFICATION_LOCK = HARNESS_DIR / "classification_lock.json"

# Route vocabulary from the B07 brief's quota table.  A locked classification
# must resolve to one of these — an unknown route is a wiring error.
KNOWN_ROUTES = frozenset(
    {
        "clarify",
        "respond",
        "inspect",
        "research",
        "requires-custom-nodes",
        "revise",
        "adapt",
        "reorganise",
    }
)


# ── deterministic helpers (the comparison contract, Flash-owned) ────────────


def _canonical_manifest_ids() -> set[str]:
    return {path.stem for path in discover_manifest_scenarios(DEFAULT_SCENARIOS_DIR)}


def _lock_entries(lock: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    """Normalize a classification lock to ``{scenario_id: entry}``.

    Accepts either a mapping keyed by scenario id or a list of entry objects
    carrying an ``id`` key — the exact container is the Pro bootstrap's choice,
    the per-entry contract (an ``id`` and a ``route``) is ours.
    """
    entries = lock.get("entries")
    if isinstance(entries, Mapping):
        normalized: dict[str, Mapping[str, Any]] = {}
        for key, value in entries.items():
            if isinstance(value, Mapping):
                normalized[str(key)] = value
        return normalized
    if isinstance(entries, (list, tuple)):
        normalized = {}
        for entry in entries:
            if isinstance(entry, Mapping) and entry.get("id"):
                normalized[str(entry["id"])] = entry
        return normalized
    raise AssertionError("classification lock 'entries' must be a mapping or a list")


def _lock_routes(lock: Mapping[str, Any]) -> dict[str, str]:
    """Return ``{scenario_id: route}`` for a lock, validating route vocabulary."""
    routes: dict[str, str] = {}
    for scenario_id, entry in _lock_entries(lock).items():
        route = entry.get("route")
        if not isinstance(route, str) or not route.strip():
            raise AssertionError(f"lock entry {scenario_id!r} has no 'route'")
        route = route.strip()
        if route not in KNOWN_ROUTES:
            raise AssertionError(f"lock entry {scenario_id!r} has unknown route {route!r}")
        routes[scenario_id] = route
    return routes


def assert_lock_complete(
    lock: Mapping[str, Any],
    scenario_ids: Iterable[str],
) -> None:
    """Every expected scenario id must have a locked classification route."""
    routes = _lock_routes(lock)
    missing = sorted(set(scenario_ids) - set(routes))
    if missing:
        preview = ", ".join(missing[:5]) + ("..." if len(missing) > 5 else "")
        raise AssertionError(
            f"lock is incomplete: {len(missing)} scenario(s) without a route: {preview}"
        )


def assert_route_equality(
    lock: Mapping[str, Any],
    summaries: Iterable[Mapping[str, Any]],
) -> None:
    """Both legs of every pair must run the locked route — identical decision.

    Each paired-leg summary carries the effective ``route``; it must equal the
    lock entry's route for the same scenario id.  A missing lock entry or a
    missing route on any leg is a lock/route wiring failure.
    """
    routes = _lock_routes(lock)
    for summary in summaries:
        scenario_id = summary.get("scenario_id")
        route = summary.get("route")
        if not isinstance(route, str) or not route.strip():
            raise AssertionError(f"summary for {scenario_id!r} records no 'route'")
        locked = routes.get(str(scenario_id))
        if locked is None:
            raise AssertionError(f"no lock entry for scenario {scenario_id!r}")
        if route != locked:
            raise AssertionError(
                f"route mismatch for {scenario_id!r}: lock says {locked!r}, "
                f"leg ran {route!r}"
            )


def assert_pairs_complete(
    summaries: Iterable[Mapping[str, Any]],
    scenario_ids: Iterable[str],
    *,
    modes: tuple[str, ...] = ("full", "two_step"),
) -> None:
    """Every scenario id must have exactly one leg per pipeline mode."""
    by_id: dict[str, dict[str, Mapping[str, Any]]] = {}
    for summary in summaries:
        scenario_id = str(summary.get("scenario_id") or "")
        mode = summary.get("pipeline_mode")
        if not scenario_id or mode not in modes:
            raise AssertionError(
                f"paired summary must carry scenario_id + pipeline_mode in {modes}; "
                f"got id={scenario_id!r}, pipeline_mode={mode!r}"
            )
        by_id.setdefault(scenario_id, {})[mode] = summary
    for scenario_id in sorted(set(scenario_ids)):
        legs = by_id.get(scenario_id, {})
        missing = [mode for mode in modes if mode not in legs]
        if missing:
            raise AssertionError(
                f"pair incomplete for {scenario_id!r}: missing {missing} leg(s)"
            )


def _is_infra_blocked(summary: Mapping[str, Any]) -> bool:
    """True only for typed/classified infra blockage — never prose-matching."""
    guard = summary.get("guard")
    if not isinstance(guard, Mapping):
        guard = {}
    failure_class = summary.get("failure_class") or guard.get("failure_class")
    score_class = summary.get("score_class") or guard.get("score_class")
    return (
        isinstance(failure_class, str) and failure_class.startswith("infra_")
    ) or score_class == "infra_blocked"


def pair_outcome(full: Mapping[str, Any], two_step: Mapping[str, Any]) -> str:
    """Classify a paired outcome: ``"pass"`` | ``"fail"`` | ``"blocked"``.

    Honesty rule: an infra-blocked leg blocks the whole pair — the pair is
    reported ``blocked`` and is never counted as a product pass or fail.  A
    pair passes only when BOTH legs succeeded.
    """
    if _is_infra_blocked(full) or _is_infra_blocked(two_step):
        return "blocked"
    full_ok = (full.get("guard") or {}).get("live_agentic_success") is True
    two_ok = (two_step.get("guard") or {}).get("live_agentic_success") is True
    if full_ok and two_ok:
        return "pass"
    return "fail"


def _synthetic_summary(
    scenario_id: str,
    *,
    mode: str,
    route: str,
    ok: bool = True,
    blocked: bool = False,
) -> dict[str, Any]:
    """A deterministic paired-leg summary.  Never touches a model."""
    summary: dict[str, Any] = {
        "scenario_id": scenario_id,
        "route": route,
        "pipeline_mode": mode,
        "status": "success" if ok else "error",
        "ok": ok,
        "output_dir": f"out/agentic/tag/{scenario_id}",
        "model_attempts": [],
        "deepseek_usage": {},
        "deepseek_est_cost_usd": 0.0,
        "deepseek_cost_basis": "not_available",
        "guard": {
            "live_agentic_success": ok,
            "score_class": "pass" if ok else "product_fail",
            "assessment": {"passed": ok, "issues": []},
        },
    }
    if mode == "two_step":
        summary["session_id"] = f"two-step-{scenario_id[:24]}"
    if blocked:
        summary["status"] = "error"
        summary["ok"] = False
        summary["failure_class"] = "infra_timeout"
        summary["score_class"] = "infra_blocked"
        summary["guard"]["live_agentic_success"] = False
        summary["guard"]["score_class"] = "infra_blocked"
    return summary


def _synthetic_lock(scenario_ids: Iterable[str], *, route: str = "revise") -> dict[str, Any]:
    return {
        "schema_version": 1,
        "scenario_count": len(list(scenario_ids)),
        "entries": {scenario_id: {"route": route} for scenario_id in scenario_ids},
    }


# ── manifest count/hash validation ──────────────────────────────────────────


def test_canonical_manifest_shape_100() -> None:
    """Anchor: the canonical lane is exactly the 100 pinned descriptors."""
    paths = discover_manifest_scenarios(DEFAULT_SCENARIOS_DIR)
    manifest = json.loads(DEFAULT_MANIFEST_PATH.read_text(encoding="utf-8"))
    entries = manifest["entries"]

    assert len(paths) == manifest["scenario_count"] == len(entries) == 100
    assert len(_canonical_manifest_ids()) == 100
    # discover_manifest_scenarios already enforces per-entry id/path/hash and
    # source-workflow hashes; assert the remaining structural invariants here.
    assert all(entry["inclusion_status"] == "included" for entry in entries)
    assert all(entry["id"] == Path(entry["path"]).stem for entry in entries)
    assert {entry["scenario_kind"] for entry in entries} <= {"edit", "semantic_product", "health_control"}


def test_two_step_50_manifest_when_present() -> None:
    """The Pro 50-lane references ALL 100 canonical descriptors; 50 included.

    Strict validation stays intact: ``discover_manifest_scenarios`` validates
    every entry (included AND excluded) for id/path/hash and source-workflow
    hashes, and rejects stray/missing descriptors.  Until the Pro bootstrap
    lands, this is skipped with an explicit marker — the canonical shape above
    is the standing anchor.
    """
    if not TWO_STEP_50_MANIFEST.is_file():
        pytest.skip(
            "two_step_50_manifest.json not yet written (Pro B07 XHARD); "
            "canonical 100 shape validated by test_canonical_manifest_shape_100"
        )

    paths = discover_manifest_scenarios(
        DEFAULT_SCENARIOS_DIR, manifest_path=TWO_STEP_50_MANIFEST
    )
    manifest = json.loads(TWO_STEP_50_MANIFEST.read_text(encoding="utf-8"))
    entries = manifest["entries"]
    included = [entry for entry in entries if entry["inclusion_status"] == "included"]
    excluded = [entry for entry in entries if entry["inclusion_status"] == "excluded"]

    assert len(paths) == len(included) == 50
    assert len(entries) == 100  # references ALL 100 canonical descriptors
    assert len(excluded) == 50
    assert {entry["id"] for entry in entries} == _canonical_manifest_ids()
    assert all(entry["id"] == Path(entry["path"]).stem for entry in entries)
    # The 50-manifest re-pins the same byte streams as the canonical manifest.
    canonical = json.loads(DEFAULT_MANIFEST_PATH.read_text(encoding="utf-8"))
    canonical_by_id = {entry["id"]: entry for entry in canonical["entries"]}
    for entry in entries:
        canonical_entry = canonical_by_id[entry["id"]]
        assert entry["descriptor_sha256"] == canonical_entry["descriptor_sha256"]
        assert (entry.get("source_workflow") or {}).get("sha256") == (
            canonical_entry.get("source_workflow") or {}
        ).get("sha256")


# ── lock completeness + route equality ──────────────────────────────────────


def test_lock_completeness_synthetic() -> None:
    ids = ["a-1", "b-2", "c-3"]
    assert_lock_complete(_synthetic_lock(ids), ids)  # no raise
    partial = _synthetic_lock(ids[:2])
    with pytest.raises(AssertionError, match="lock is incomplete"):
        assert_lock_complete(partial, ids)
    # Unknown route vocabulary is a wiring error, not a silent pass.
    bad = _synthetic_lock(ids)
    bad["entries"]["a-1"]["route"] = "not-a-route"
    with pytest.raises(AssertionError, match="unknown route"):
        assert_lock_complete(bad, ids)


def test_route_equality_synthetic() -> None:
    ids = ["a-1", "b-2"]
    lock = _synthetic_lock(ids, route="revise")
    summaries = [
        _synthetic_summary("a-1", mode="full", route="revise"),
        _synthetic_summary("a-1", mode="two_step", route="revise"),
        _synthetic_summary("b-2", mode="full", route="revise"),
        _synthetic_summary("b-2", mode="two_step", route="revise"),
    ]
    assert_route_equality(lock, summaries)  # no raise

    divergent = [dict(summaries[0]), dict(summaries[0])]
    divergent[1]["route"] = "inspect"
    with pytest.raises(AssertionError, match="route mismatch"):
        assert_route_equality(lock, divergent)

    with pytest.raises(AssertionError, match="no lock entry"):
        assert_route_equality(lock, [_synthetic_summary("ghost", mode="full", route="revise")])


def test_lock_completeness_live_lock_when_present() -> None:
    """The frozen classification lock must cover the lane's scenario ids.

    Runs only once the Pro bootstrap has written ``classification_lock.json``;
    the lane is the 50-manifest when it exists, else the canonical 100.
    """
    if not CLASSIFICATION_LOCK.is_file():
        pytest.skip("classification_lock.json not yet written (Pro B07 bootstrap)")
    lock = json.loads(CLASSIFICATION_LOCK.read_text(encoding="utf-8"))
    if TWO_STEP_50_MANIFEST.is_file():
        manifest = json.loads(TWO_STEP_50_MANIFEST.read_text(encoding="utf-8"))
        lane_ids = {
            entry["id"] for entry in manifest["entries"] if entry["inclusion_status"] == "included"
        }
    else:
        lane_ids = _canonical_manifest_ids()
    assert_lock_complete(lock, lane_ids)
    assert len(_lock_routes(lock)) >= len(lane_ids)


# ── pair completeness ───────────────────────────────────────────────────────


def test_pair_completeness_synthetic() -> None:
    ids = ["a-1", "b-2", "c-3"]
    summaries = [
        _synthetic_summary(sid, mode=mode, route="revise")
        for sid in ids
        for mode in ("full", "two_step")
    ]
    assert_pairs_complete(summaries, ids)  # no raise

    dropped = [summary for summary in summaries if not (summary["scenario_id"] == "b-2" and summary["pipeline_mode"] == "two_step")]
    with pytest.raises(AssertionError, match="pair incomplete"):
        assert_pairs_complete(dropped, ids)

    # A leg whose pipeline_mode is not one of the paired modes is a wiring error.
    rogue = _synthetic_summary("a-1", mode="full", route="revise")
    rogue["pipeline_mode"] = "research"
    with pytest.raises(AssertionError, match="pipeline_mode"):
        assert_pairs_complete([rogue], ["a-1"])


def test_pair_completeness_live_run_when_present() -> None:
    """After the host's live run, every paired summary must have both legs."""
    run_summary = Path("out/agentic/two-step-50/run_summary.json")
    if not run_summary.is_file():
        pytest.skip(
            "live two-step-50 paired run not yet executed (host runs it after "
            "the final sense-check)"
        )
    payload = json.loads(run_summary.read_text(encoding="utf-8"))
    summaries = payload.get("scenarios", [])
    if TWO_STEP_50_MANIFEST.is_file():
        manifest = json.loads(TWO_STEP_50_MANIFEST.read_text(encoding="utf-8"))
        lane_ids = {
            entry["id"] for entry in manifest["entries"] if entry["inclusion_status"] == "included"
        }
    else:
        lane_ids = _canonical_manifest_ids()
    assert_pairs_complete(summaries, lane_ids)


# ── comparator behavior WITHOUT model calls ────────────────────────────────


def test_comparison_bookkeeping_without_model_calls() -> None:
    """Full comparison bookkeeping on synthetic pairs — zero model calls.

    This is the deterministic core of the comparator: lock completeness,
    route equality, pair completeness, and outcome classification all run on
    in-memory dicts.  The result must also be JSON-serializable so the
    per-scenario/aggregate reports can be persisted.
    """
    ids = ["a-1", "b-2", "c-3"]
    lock = _synthetic_lock(ids, route="revise")
    summaries = [
        _synthetic_summary(sid, mode=mode, route="revise")
        for sid in ids
        for mode in ("full", "two_step")
    ]
    summaries[0]["ok"] = False  # full leg of a-1 fails as a product failure
    summaries[0]["guard"]["live_agentic_success"] = False

    assert_lock_complete(lock, ids)
    assert_route_equality(lock, summaries)
    assert_pairs_complete(summaries, ids)

    outcomes = {
        scenario_id: pair_outcome(
            next(s for s in summaries if s["scenario_id"] == scenario_id and s["pipeline_mode"] == "full"),
            next(s for s in summaries if s["scenario_id"] == scenario_id and s["pipeline_mode"] == "two_step"),
        )
        for scenario_id in ids
    }
    assert outcomes == {"a-1": "fail", "b-2": "pass", "c-3": "pass"}
    # The aggregate must be persistable without model calls.
    json.dumps({"outcomes": outcomes, "summaries": summaries}, default=str)


def test_pro_comparator_module_when_present() -> None:
    """The Pro comparator module must import and expose its CLI entry point.

    Exercising the real module is a model-call-free structural check: the
    module is a pure CLI (``python -m ... --validate-only`` is in the B07
    gate), so importing it must not require network access.  Skipped until
    the Pro XHARD comparator lands.
    """
    module = pytest.importorskip("tests.live_agentic_harness.compare_pipeline_modes")
    assert callable(getattr(module, "main", None)), (
        "compare_pipeline_modes must expose main() for `python -m ...`"
    )


# ── honest treatment of blocked provider/infra results ─────────────────────


def test_blocked_leg_blocks_pair_and_never_counts_as_product_result() -> None:
    """An infra-blocked leg makes the pair 'blocked' — never pass, never fail."""
    # (a) full blocked, two-step passed -> pair is blocked, NOT pass.
    full = _synthetic_summary("a-1", mode="full", route="revise", blocked=True)
    two = _synthetic_summary("a-1", mode="two_step", route="revise", ok=True)
    assert pair_outcome(full, two) == "blocked"
    # (b) both blocked -> blocked.
    assert pair_outcome(
        _synthetic_summary("b-2", mode="full", route="revise", blocked=True),
        _synthetic_summary("b-2", mode="two_step", route="revise", blocked=True),
    ) == "blocked"
    # (c) product fail + blocked leg -> blocked, not fail (no product verdict).
    assert pair_outcome(
        _synthetic_summary("c-3", mode="full", route="revise", ok=False),
        _synthetic_summary("c-3", mode="two_step", route="revise", blocked=True),
    ) == "blocked"
    # (d) both pass -> pass (sanity, so 'blocked' is not the default).
    assert pair_outcome(
        _synthetic_summary("d-4", mode="full", route="revise", ok=True),
        _synthetic_summary("d-4", mode="two_step", route="revise", ok=True),
    ) == "pass"


def test_infra_blocked_requires_typed_evidence_not_prose() -> None:
    """Blocked classification must come from typed failure_class/score_class.

    A summary whose error prose merely mentions a provider outage — with no
    typed ``failure_class``/``score_class`` and no model_attempts evidence —
    must stay a product result.  Absence of evidence is not infrastructure,
    mirroring the runner's canonical-evidence rule.
    """
    summary = _synthetic_summary("a-1", mode="full", route="revise", ok=False)
    summary["error"] = "OpenRouter is down, the provider is overloaded, 429 everywhere"
    assert _is_infra_blocked(summary) is False
    assert pair_outcome(
        summary,
        _synthetic_summary("a-1", mode="two_step", route="revise", ok=True),
    ) == "fail"

    # Typed evidence (model_attempts failure_type=empty_response + 0 tokens)
    # is what the runner reclassifies; the comparator must honor the typed
    # result without re-litigating prose.
    typed = _synthetic_summary("a-1", mode="full", route="revise", ok=False)
    typed["failure_class"] = "infra_empty_response"
    typed["score_class"] = "infra_blocked"
    typed["model_attempts"] = [
        {
            "phase": "classify",
            "outcome": "failure",
            "failure_type": "empty_response",
            "token_usage": {"completion_tokens": 0},
        }
    ]
    assert _is_infra_blocked(typed) is True
    assert pair_outcome(typed, _synthetic_summary("a-1", mode="two_step", route="revise", ok=True)) == "blocked"


# ── runner/adapter pipeline-mode wiring (deterministic, no model calls) ─────


def test_two_step_session_id_stable_and_path_safe() -> None:
    first = _two_step_session_id("image-qwen-image-inpainting-with-controlnet-09fc64")
    again = _two_step_session_id("image-qwen-image-inpainting-with-controlnet-09fc64")
    assert first == again  # stable across attempts/runs of the same window
    assert first.startswith("two-step-")
    assert len(first) == len("two-step-") + 24
    assert first.replace("-", "").isalnum()  # single safe path component
    # Different scenarios never share a session id (no cross-contamination).
    assert first != _two_step_session_id("image-qwen-image-inpainting-with-controlnet-09fc65")


def test_resolve_pipeline_mode_explicit_over_descriptor() -> None:
    scenario = {"id": "x", "pipeline_mode": "two_step"}
    assert _resolve_pipeline_mode(None, scenario) == "two_step"
    assert _resolve_pipeline_mode("full", scenario) == "full"  # flag wins
    assert _resolve_pipeline_mode(None, {"id": "x"}) is None  # product default
    assert _resolve_pipeline_mode(None, {"id": "x", "_tags": {"pipeline_mode": "two_step"}}) == "two_step"
    from vibecomfy.executor.contracts import PipelineModeRequestError

    with pytest.raises(PipelineModeRequestError):
        _resolve_pipeline_mode("bogus", scenario)
    with pytest.raises(PipelineModeRequestError):
        _resolve_pipeline_mode(None, {"id": "x", "pipeline_mode": "bogus"})


def test_pipeline_mode_flag_reaches_child_and_pins_env(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """Sense-check: --pipeline-mode reaches the child command line and the
    child environment is pinned against ambient VIBECOMFY_EXECUTOR_PIPELINE_MODE."""
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    (scenarios_dir / "two-step.json").write_text(
        json.dumps({"id": "two-step", "query": "do it"}), encoding="utf-8"
    )
    monkeypatch.setenv(_PIPELINE_MODE_ENV_VAR, "full")
    captured: dict = {}

    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202, ARG001
        captured["cmd"] = list(cmd)
        captured["env"] = dict(kwargs.get("env") or {})
        out_file = Path(cmd[cmd.index("--single-out") + 1])
        tag = cmd[cmd.index("--tag") + 1]
        payload = {
            "scenario_id": "two-step",
            "status": "success",
            "ok": True,
            "output_dir": str(tmp_path / "out" / tag / "two-step"),
            "pipeline_mode": "two_step",
            "guard": {"live_agentic_success": True},
            "model_attempts": [],
            "deepseek_usage": {},
            "deepseek_est_cost_usd": 0.0,
            "deepseek_cost_basis": "not_available",
        }
        out_file.write_text(json.dumps(payload), encoding="utf-8")
        return (0, "", "")

    write_manifest(scenarios_dir)
    monkeypatch.setattr("tests.live_agentic_harness.runner._run_scenario_subprocess", fake_run)

    summary = run_tag(
        "tag",
        scenarios_dir=scenarios_dir,
        output_base=tmp_path / "out",
        max_workers=1,
        per_scenario_timeout=1,
        infra_retries=0,
        progress_every=0,
        pipeline_mode="two_step",
    )

    assert captured["cmd"][captured["cmd"].index("--pipeline-mode") + 1] == "two_step"
    assert _PIPELINE_MODE_ENV_VAR not in captured["env"]  # ambient pin stripped
    assert summary["pipeline_mode"] == "two_step"
    assert summary["scenarios"][0]["pipeline_mode"] == "two_step"


def test_pipeline_mode_omitted_passes_through_ambient_pin() -> None:
    """No explicit flag -> the ambient VIBECOMFY_EXECUTOR_PIPELINE_MODE is
    deliberately preserved (operator pin), and no --pipeline-mode flag is
    added to the child command line."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv(_PIPELINE_MODE_ENV_VAR, "two_step")
    try:
        env = _pinned_child_env("openrouter", None)
        assert env[_PIPELINE_MODE_ENV_VAR] == "two_step"
    finally:
        monkeypatch.undo()
    parser = _build_parser()
    args = parser.parse_args(["--tag", "t"])
    assert args.pipeline_mode is None


def test_pinned_child_env_strips_pipeline_mode_only_when_explicit() -> None:
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv(_PIPELINE_MODE_ENV_VAR, "full")
    monkeypatch.setenv("OPENROUTER_API_KEY", "keep-me")
    try:
        env = _pinned_child_env("openrouter", "two_step")
        assert _PIPELINE_MODE_ENV_VAR not in env
        assert env["OPENROUTER_API_KEY"] == "keep-me"  # credentials preserved
        # Transport-selecting keys are pinned away too (the explicit selector
        # is the only authority; the adapter re-establishes them in the child).
        assert "VIBECOMFY_TRANSPORT" not in env
        assert "VIBECOMFY_OPENROUTER_BASE_URL" not in env
    finally:
        monkeypatch.undo()


# ── second comparator selection: the 57-ledger lane ─────────────────────────


def test_ledger_second_comparator_selection() -> None:
    """The second comparator lane is ledger_scenario_ids() — 57 unique ids,
    all of which are canonical 100 descriptors."""
    assert_ledger_integrity()
    ids = ledger_scenario_ids()
    assert len(ids) == LEDGER_ID_COUNT == 57
    assert len(set(ids)) == 57
    assert set(ids) <= _canonical_manifest_ids()
    # The selection helper enforces the same invariants at the single source.
    assert ledger_selection_ids() == ids


def test_ledger_labels_current_and_v3_only() -> None:
    """Ledger label contract: `current` resolves to `ir-everywhere-57-v3`;
    the legacy `ir-everywhere-57` label is INVALID and must be rejected."""
    assert resolve_ledger_label(None) == LEDGER_ARTIFACT_LABEL == "ir-everywhere-57-v3"
    assert resolve_ledger_label(LEDGER_LABEL_CURRENT) == LEDGER_ARTIFACT_LABEL
    assert resolve_ledger_label("ir-everywhere-57-v3") == "ir-everywhere-57-v3"
    assert LEDGER_LABEL_CURRENT == "current"
    assert "ir-everywhere-57" in INVALID_LEGACY_LEDGER_LABELS
    for invalid in ("ir-everywhere-57", "ir-everywhere-57-v2"):
        with pytest.raises(LedgerLabelError, match="INVALID legacy label"):
            resolve_ledger_label(invalid)
    with pytest.raises(LedgerLabelError, match="unknown ledger label"):
        resolve_ledger_label("ir-everywhere-57-v4")


def test_ledger_lane_overlaps_50_lane_when_manifest_present() -> None:
    """B07 quota: exactly 25 of the 50-lane ids are in the 57-ledger lane
    (so the 50 ∩ 57 overlap is cached and never billed twice)."""
    if not TWO_STEP_50_MANIFEST.is_file():
        pytest.skip("two_step_50_manifest.json not yet written (Pro B07 XHARD)")
    manifest = json.loads(TWO_STEP_50_MANIFEST.read_text(encoding="utf-8"))
    lane_ids = {
        entry["id"] for entry in manifest["entries"] if entry["inclusion_status"] == "included"
    }
    overlap = lane_ids & set(ledger_scenario_ids())
    assert len(overlap) == 25
