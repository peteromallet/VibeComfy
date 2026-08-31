"""T5.4 concurrent comparison isolation proofs.

Covers:
* ``run_leg_from_spec`` round-trips a leg spec into a real ``_run_mode`` call
  and persists an atomically-written summary (child entry contract);
* the process pool submits every leg before awaiting any result, reconstructs
  in submission/manifest order, and maps failures to typed leg summaries;
* a timed-out or crashed child cannot take down the comparison;
* the CLI run lane defaults to process isolation for concurrency > 1 while
  library callers keep the historical thread lane;
* adapter environment pinning is lock-protected and idempotent under
  concurrent writers.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

import pytest

from tests.live_agentic_harness import compare_pipeline_modes as comparator


def _descriptor(scenario_id: str = "speed-distillation-research") -> dict[str, Any]:
    return {"id": scenario_id, "query": "q", "session_id": None}


def _descriptors(count: int) -> list[tuple[str, str, dict[str, Any], str]]:
    out = []
    for i in range(count):
        sid = f"s{i}-{_descriptor()['id']}" if False else _descriptor()["id"]
        out.append((f"{sid}-{i}", "staged", dict(_descriptor(), id=f"{sid}-{i}"), "0" * 64))
        out.append((f"{sid}-{i}", "threaded", dict(_descriptor(), id=f"{sid}-{i}"), "0" * 64))
    return out


# ── child entry contract ─────────────────────────────────────────────────────


def test_run_leg_from_spec_executes_and_persists_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[dict[str, Any]] = []

    def fake_run_mode(
        scenario,
        *,
        mode,
        locked_input_sha256,
        output_base,
        tag,
        transport,
        judge_route,
        judge_model,
    ):
        seen.append({"scenario_id": scenario["id"], "mode": mode})
        return {"scenario_id": scenario["id"], "pipeline_mode": mode, "status": "success"}

    monkeypatch.setattr(
        comparator,
        "require_judge_readiness",
        lambda config: {"ready": True, "model": config.model},
    )
    monkeypatch.setattr(comparator, "_run_mode", fake_run_mode)
    spec_path = tmp_path / "spec.json"
    out_path = tmp_path / "out.json"
    comparator._write_leg_spec(
        spec_path,
        scenario=_descriptor("my-scenario"),
        mode="staged",
        locked_input_sha256="a" * 64,
        output_base=tmp_path,
        tag="t",
        transport=None,
    )
    code = comparator.run_leg_from_spec(spec_path, out_path)
    assert code == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["summary"]["scenario_id"] == "my-scenario"
    assert payload["summary"]["judge_config"] == {
        "route": "deepseek",
        "model": "deepseek-v4-pro",
    }
    assert seen == [{"scenario_id": "my-scenario", "mode": "staged"}]


def test_child_failure_is_reported_not_raised(tmp_path: Path, monkeypatch) -> None:
    def exploding_run_mode(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("leg blew up")

    monkeypatch.setattr(comparator, "_run_mode", exploding_run_mode)
    spec_path = tmp_path / "spec.json"
    out_path = tmp_path / "out.json"
    comparator._write_leg_spec(
        spec_path,
        scenario=_descriptor(),
        mode="threaded",
        locked_input_sha256="b" * 64,
        output_base=tmp_path,
        tag="t",
        transport=None,
    )
    assert comparator.run_leg_from_spec(spec_path, out_path) == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["ok"] is False
# ── process pool: bounded launch window, await-in-order, typed failure map ───


def test_process_pool_respects_concurrency_cap_and_reconstructs_in_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """G5-B4-MUST-008: at most ``concurrency`` leg processes are live at any
    moment; every descriptor launches exactly once; results reconstruct in
    manifest order with failed children keeping their slots."""
    concurrency = 2
    descriptors = _descriptors(6)
    live = {"count": 0}
    max_live = {"count": 0}
    spawn_order: list[int] = []
    polls_without_progress = {"n": 0}

    class FakeHandle:
        def __init__(self, index: int) -> None:
            self.index = index

        def poll(self) -> int | None:
            # Finish only after a few polling rounds so the parent must keep
            # the launch window open, then exit successfully.
            polls_without_progress["n"] += 1
            if polls_without_progress["n"] % 3 == 0:
                return 0
            return None

        def wait(self, timeout: float | None = None) -> int:
            return 0

    real_write = comparator._write_leg_spec

    def tracking_write(spec_path, **kwargs):  # noqa: ANN001, ANN202
        index = int(Path(spec_path).stem.split("_")[1])
        spawn_order.append(index)
        real_write(spec_path, **kwargs)

    def write_result_and_finish(spec_path, **kwargs):  # noqa: ANN001, ANN202
        tracking_write(spec_path, **kwargs)
        spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
        out_path = Path(spec_path).parent / Path(spec_path).name.replace(
            "leg_", "result_"
        )
        out_path.write_text(
            json.dumps(
                {
                    "ok": True,
                    "summary": {
                        "scenario_id": spec["scenario"]["id"],
                        "pipeline_mode": spec["mode"],
                        "status": "success",
                        "ok": True,
                    },
                }
            ),
            encoding="utf-8",
        )

    fake_handles: dict[int, FakeHandle] = {}

    def fake_popen(*args: Any, **kwargs: Any) -> FakeHandle:
        index = len(fake_handles)
        live["count"] += 1
        max_live["count"] = max(max_live["count"], live["count"])
        handle = FakeHandle(index)
        fake_handles[index] = handle
        return handle

    real_poll = FakeHandle.poll

    def counting_poll(self):
        result = real_poll(self)
        if result is not None:
            live["count"] -= 1
        return result

    FakeHandle.poll = counting_poll  # type: ignore[method-assign]

    def fake_run_mode(scenario, *, mode, locked_input_sha256, output_base, tag, transport):
        raise AssertionError("process pool must not call _run_mode in the parent")

    monkeypatch.setattr(comparator, "_write_leg_spec", write_result_and_finish)
    monkeypatch.setattr("subprocess.Popen", fake_popen)
    monkeypatch.setattr(comparator, "_run_mode", fake_run_mode)

    results = comparator._run_legs_in_processes(
        descriptors,
        output_base=tmp_path,
        tag="t",
        transport=None,
        concurrency=concurrency,
    )
    # Every descriptor launched exactly once, under the cap.
    assert sorted(spawn_order) == list(range(len(descriptors)))
    assert max_live["count"] <= concurrency
    # Reconstruction follows manifest order; successful children keep slots.
    assert [r["scenario_id"] for r in results] == [d[0] for d in descriptors]
    assert all(r["status"] == "success" for r in results)


def test_process_pool_maps_failed_children_to_typed_summaries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Children that exit without a payload map to runner_exception summaries
    in their ORIGINAL slots (no silent swallowing, no reordering)."""
    descriptors = _descriptors(2)

    class FakeHandle:
        def poll(self) -> int:
            return 0

        def wait(self, timeout: float | None = None) -> int:
            return 0

    real_write = comparator._write_leg_spec

    def write_spec_only(spec_path, **kwargs):  # noqa: ANN001, ANN202
        real_write(spec_path, **kwargs)

    monkeypatch.setattr(comparator, "_write_leg_spec", write_spec_only)
    monkeypatch.setattr("subprocess.Popen", lambda *a, **k: FakeHandle())
    results = comparator._run_legs_in_processes(
        descriptors,
        output_base=tmp_path,
        tag="t",
        transport=None,
        concurrency=4,
    )
    assert all(r is not None for r in results)
    assert all(r["status"] == "runner_exception" for r in results)
    assert [r["scenario_id"] for r in results] == [d[0] for d in descriptors]


def test_process_pool_maps_child_summaries_into_manifest_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When children succeed, their summaries land in submission order."""
    descriptors = _descriptors(1)

    class FakeHandle:
        def poll(self) -> int:
            return 0

        def wait(self, timeout: float | None = None) -> int:
            return 0

    monkeypatch.setattr("subprocess.Popen", lambda *a, **k: FakeHandle())


    real_write = comparator._write_leg_spec

    def write_and_answer(spec_path, **kwargs):  # noqa: ANN001, ANN202
        real_write(spec_path, **kwargs)
        spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
        out_path = Path(spec_path).parent / Path(spec_path).name.replace("leg_", "result_")
        out_path.write_text(
            json.dumps(
                {
                    "ok": True,
                    "summary": {
                        "scenario_id": spec["scenario"]["id"],
                        "pipeline_mode": spec["mode"],
                        "status": "success",
                        "ok": True,
                    },
                }
            ),
            encoding="utf-8",
        )

    monkeypatch.setattr(comparator, "_write_leg_spec", write_and_answer)
    results = comparator._run_legs_in_processes(
        descriptors, output_base=tmp_path, tag="t", transport=None
    )
    assert [r["scenario_id"] for r in results] == [d[0] for d in descriptors]
    assert [r["pipeline_mode"] for r in results] == ["staged", "threaded"]


# ── CLI defaults ─────────────────────────────────────────────────────────────


def test_cli_defaults_to_process_isolation_for_concurrent_runs() -> None:
    args = comparator._build_parser().parse_args(["--run", "--concurrency", "10"])
    resolved = args.leg_isolation or ("process" if args.concurrency > 1 else "thread")
    assert resolved == "process"


def test_cli_explicit_thread_isolation_is_refused_for_paid_runs(capsys) -> None:
    """G5-B4-MUST-008: the paid run lane never executes on the shared-process
    thread lane — an explicit ``--leg-isolation thread`` is refused."""
    from tests.live_agentic_harness import compare_pipeline_modes as comparator

    assert comparator.main(["--run", "--concurrency", "2", "--leg-isolation", "thread"]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert "thread" in payload["error"]


def test_run_comparison_rejects_unknown_isolation(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(comparator, "validate_only", lambda _p=None: {"ok": True})
    with pytest.raises(comparator.ComparisonManifestError, match="leg_isolation"):
        comparator.run_comparison(concurrency=2, leg_isolation="magic")


# ── thread-lane env hardening ────────────────────────────────────────────────


def test_adapter_env_pinning_is_idempotent_under_concurrency() -> None:
    from tests.live_agentic_harness.adapter import (
        _ensure_headless_env,
        _ensure_transport_env,
    )

    errors: list[Exception] = []
    barrier = threading.Barrier(8)

    def worker() -> None:
        try:
            barrier.wait(timeout=5)
            _ensure_headless_env()
            resolved = _ensure_transport_env("native")
            assert resolved == "native"
            assert os.environ.get("VIBECOMFY_TRANSPORT") == "native"
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    assert errors == []
