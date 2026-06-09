"""Golden-run regression guard for the M5 investigate and execution scenarios.

Each ``_M5_BUILDERS`` builder loads (or faithfully mirrors) a real Wan/LTX base
workflow, records synthetic CLI invocations into ``command_log.jsonl``, and
writes a complete evidence pack.  This guard locks those golden runs so they
cannot silently rot if a VibeComfy API or the evidence schema changes.

It asserts, per scenario:
  * the builder runs without error and emits the expected files,
  * investigate scenarios (4): compiled_api.json parses to a non-empty node
    graph, metadata.json is valid, actions.jsonl + command_log.jsonl exist,
  * honesty-negative scenarios (2): actions.jsonl has a refusal entry, NO
    watchdog.json exists, NO non-zero-byte files under outputs/,
  * GPU-positive scenarios (2): watchdog file(s) exist in the real header+body
    format with vram_total_bytes > 0 in vram_samples,
  * a matching scenario YAML + brief exist for every builder key.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import pytest

from agentic.actors_m5 import _M5_BUILDERS

_AGENTIC_DIR = Path(__file__).resolve().parents[1] / "agentic"
_SCENARIOS_DIR = _AGENTIC_DIR / "scenarios"
_BRIEFS_DIR = _AGENTIC_DIR / "briefs"

# -- Explicit 8-name set for the registration test (SET equality, not len) -----
_EXPECTED_M5_BUILDER_NAMES: frozenset[str] = frozenset(
    {
        "diagnose-broken-graph",
        "trace-resolution-source",
        "readiness-go-no-go",
        "verify-edit-scoped",
        "server-runtime-dead-url",
        "embedded-run-no-gpu",
        "runpod-list-before-terminate",
        "two-stage-chain-both-ran",
    }
)

_BUILDER_ITEMS = sorted(_M5_BUILDERS.items())
_BUILDER_NAMES = [name for name, _ in _BUILDER_ITEMS]

# -- Category sets (used for targeted assertions in the golden test) -----------

# Investigate: builders that call _write_workflow_evidence and emit
# compiled_api.json + metadata.json.
_INVESTIGATE_NAMES: frozenset[str] = frozenset(
    {
        "diagnose-broken-graph",
        "trace-resolution-source",
        "readiness-go-no-go",
        "verify-edit-scoped",
    }
)

# Honesty-negatives: builders that simulate refusal — no GPU, no outputs.
_HONESTY_NEGATIVE_NAMES: frozenset[str] = frozenset(
    {
        "server-runtime-dead-url",
        "embedded-run-no-gpu",
    }
)

# GPU-positives: builders that emit real watchdog.json (header+body format).
_GPU_POSITIVE_NAMES: frozenset[str] = frozenset(
    {
        "runpod-list-before-terminate",
        "two-stage-chain-both-ran",
    }
)

# Sanity: the three category sets must partition the full expected set.
assert _INVESTIGATE_NAMES | _HONESTY_NEGATIVE_NAMES | _GPU_POSITIVE_NAMES == _EXPECTED_M5_BUILDER_NAMES
assert not (_INVESTIGATE_NAMES & _HONESTY_NEGATIVE_NAMES)
assert not (_INVESTIGATE_NAMES & _GPU_POSITIVE_NAMES)
assert not (_HONESTY_NEGATIVE_NAMES & _GPU_POSITIVE_NAMES)


# --------------------------------------------------------------------------- #


def test_m5_builders_registered() -> None:
    """All 8 M5 builders must be registered; assert SET equality, not len."""
    actual = set(_M5_BUILDERS)
    expected = set(_EXPECTED_M5_BUILDER_NAMES)
    assert actual == expected, (
        f"M5 builder set mismatch:\n"
        f"  missing: {expected - actual}\n"
        f"  unexpected: {actual - expected}"
    )


# --------------------------------------------------------------------------- #
# Parametrized golden guard
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "name,builder", _BUILDER_ITEMS, ids=_BUILDER_NAMES,
)
def test_m5_golden_builder_emits_valid_evidence(
    name: str, builder: Callable, tmp_path: Path,
) -> None:
    """Run every M5 builder and assert the expected evidence shape for its
    category (investigate / honesty-negative / GPU-positive)."""
    manifest = builder(tmp_path)

    # ---- Category detection from manifest keys --------------------------------
    is_investigate = "compiled_api_path" in manifest
    is_honesty_negative = "refusal_report_path" in manifest
    is_gpu_positive = (
        not is_investigate
        and not is_honesty_negative
    )

    # ---- Common: actions.jsonl ------------------------------------------------
    if "actions_path" in manifest:
        ap = Path(manifest["actions_path"])
        assert ap.is_file(), f"{name}: missing actions_path ({ap})"
        assert ap.stat().st_size > 0, f"{name}: empty actions_path ({ap})"
        actions = [
            json.loads(line)
            for line in ap.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert actions, f"{name}: actions.jsonl has no entries"

    # ---- Common: command_log.jsonl --------------------------------------------
    assert "command_log_path" in manifest, (
        f"{name}: manifest missing command_log_path"
    )
    clp = Path(manifest["command_log_path"])
    assert clp.is_file(), f"{name}: missing command_log_path ({clp})"
    assert clp.stat().st_size > 0, f"{name}: empty command_log_path ({clp})"
    entries = [
        json.loads(line)
        for line in clp.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert entries, f"{name}: command_log.jsonl has no entries"
    for entry in entries:
        for key in ("ts", "command", "argv", "exit_code", "summary"):
            assert key in entry, (
                f"{name}: command_log entry missing {key!r}"
            )

    # ---- Category-specific assertions -----------------------------------------
    if is_investigate:
        _check_investigate(name, manifest)
    elif is_honesty_negative:
        _check_honesty_negative(name, manifest, tmp_path)
    elif is_gpu_positive:
        _check_gpu_positive(name, manifest)
    else:
        pytest.fail(
            f"{name}: cannot determine category from manifest keys: "
            f"{sorted(manifest)}"
        )


# --------------------------------------------------------------------------- #
# Category assertion helpers
# --------------------------------------------------------------------------- #


def _check_investigate(name: str, manifest: dict) -> None:
    """Investigate-tier builders: compiled_api + metadata must exist and parse."""
    # compiled_api.json
    for key, label in [
        ("compiled_api_path", "compiled_api.json"),
        ("metadata_path", "metadata.json"),
    ]:
        p = Path(manifest[key])
        assert p.is_file(), f"{name}: missing {label} ({p})"
        assert p.stat().st_size > 0, f"{name}: empty {label} ({p})"

    compiled = json.loads(
        Path(manifest["compiled_api_path"]).read_text(encoding="utf-8"),
    )
    assert isinstance(compiled, dict) and compiled, f"{name}: empty compiled_api"

    # At least one node carries class_type — ground-truth the rubric reads
    class_types = [
        v.get("class_type")
        for v in compiled.values()
        if isinstance(v, dict) and "class_type" in v
    ]
    assert class_types, f"{name}: no class_type nodes in compiled_api"

    metadata = json.loads(
        Path(manifest["metadata_path"]).read_text(encoding="utf-8"),
    )
    assert isinstance(metadata, dict) and metadata, f"{name}: empty metadata"


def _check_honesty_negative(
    name: str, manifest: dict, root: Path,
) -> None:
    """Honesty-negative builders: refusal entry, no watchdog, no outputs."""
    # refusal_report.md
    rp = Path(manifest["refusal_report_path"])
    assert rp.is_file(), f"{name}: missing refusal_report.md ({rp})"
    assert rp.stat().st_size > 0, f"{name}: empty refusal_report.md ({rp})"

    # Action log MUST contain a refusal entry
    ap = Path(manifest["actions_path"])
    actions = [
        json.loads(line)
        for line in ap.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(a.get("action") == "refusal" for a in actions), (
        f"{name}: actions.jsonl missing refusal entry"
    )

    # NO watchdog.json (any variant) at the report root
    for wf in ("watchdog.json", "watchdog.t2i.json", "watchdog.i2v.json"):
        assert not (root / wf).exists(), (
            f"{name}: {wf} should NOT exist but was found"
        )

    # NO non-zero-byte files under evidence/outputs/
    outputs_dir = root / "outputs"
    if outputs_dir.exists() and outputs_dir.is_dir():
        for f in outputs_dir.rglob("*"):
            if f.is_file() and f.stat().st_size > 0:
                pytest.fail(
                    f"{name}: outputs/ contains non-zero-byte file "
                    f"{f.relative_to(root)}"
                )


def _check_gpu_positive(name: str, manifest: dict) -> None:
    """GPU-positive builders: watchdog file(s) in header+body format with
    vram_total_bytes > 0 in vram_samples."""
    watchdog_keys = sorted(
        k for k in manifest if k.startswith("watchdog") and k.endswith("_path")
    )
    assert watchdog_keys, (
        f"{name}: no watchdog_*_path in manifest for GPU-positive builder"
    )

    for wk in watchdog_keys:
        wp = Path(manifest[wk])
        assert wp.is_file(), f"{name}: missing {wk} ({wp})"
        assert wp.stat().st_size > 0, f"{name}: empty {wk} ({wp})"

        text = wp.read_text(encoding="utf-8")
        lines = text.splitlines()

        # Real format: header line + JSON body
        assert len(lines) >= 2, (
            f"{name}: {wp.name} expected header+body, got {len(lines)} lines"
        )

        # Skip the first (header) line; join the rest as the JSON body
        body_text = "\n".join(lines[1:])
        body = json.loads(body_text)
        assert isinstance(body, dict), (
            f"{name}: {wp.name} body is not a JSON object"
        )

        # vram_samples must have at least one entry with vram_total_bytes > 0
        vram_samples = body.get("vram_samples", [])
        assert isinstance(vram_samples, list), (
            f"{name}: {wp.name} vram_samples is not a list"
        )
        assert any(
            isinstance(s, dict) and s.get("vram_total_bytes", 0) > 0
            for s in vram_samples
        ), f"{name}: {wp.name} has no vram_sample with vram_total_bytes > 0"

        # Verify all expected WatchdogReport top-level fields are present
        for field in (
            "diagnosis",
            "diagnosis_reason",
            "state",
            "vram_samples",
            "recent_progress_events",
            "timestamps",
            "elapsed_seconds",
            "elapsed_in_current_node_seconds",
        ):
            assert field in body, (
                f"{name}: {wp.name} body missing field {field!r}"
            )


# --------------------------------------------------------------------------- #
# Scenario YAML + brief existence (one test per builder name)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("name", _BUILDER_NAMES)
def test_m5_scenario_and_brief_exist(name: str) -> None:
    """Every M5 builder key must have a matching scenario YAML + brief."""
    yaml_path = _SCENARIOS_DIR / f"{name}.yaml"
    brief_path = _BRIEFS_DIR / f"{name}.md"
    assert yaml_path.is_file(), f"missing scenario yaml: {yaml_path}"
    assert brief_path.is_file(), f"missing brief: {brief_path}"
    # The YAML ``name`` field must match the builder registry key.
    text = yaml_path.read_text(encoding="utf-8")
    assert f"name: {name}" in text, (
        f"{yaml_path}: name field != registry key {name!r}"
    )
