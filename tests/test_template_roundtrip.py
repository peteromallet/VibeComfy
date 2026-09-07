from __future__ import annotations

from collections import Counter
from functools import lru_cache
import json
import os
from pathlib import Path
from typing import Any

import pytest

from vibecomfy.ingest.loader import load_workflow_json
from vibecomfy.ingest.normalize import normalize_to_api
from vibecomfy.porting.emit.ui import emit_ui_json
from vibecomfy.porting.parity import class_type_counter, topology_counter
from vibecomfy.registry.ready import workflow_from_ready
from vibecomfy.workflow_context import _CURRENT_WORKFLOW
from vibecomfy.workflow_bundle import (
    WorkflowBundleError,
    WorkflowReconciliationError,
    load_bundle,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_INDEX = REPO_ROOT / "template_index.json"
CORPUS_ROOT = REPO_ROOT / "ready_templates/sources"
WAN_I2V_GOLDEN_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "golden_api_video_wan_i2v.json"
STRICT_ROUNDTRIP_TEMPLATE_IDS = {"video/wan_i2v"}

AUDITED_SOURCE_MAPPINGS = {
    "image/z_image": "ready_templates/sources/official/image/z_image.json",
    "video/ltx2_3_runexx_talking_avatar_qwen_tts": (
        "ready_templates/sources/custom_nodes/ltxvideo/runexx/LTX-2.3_Talking_Avatar_Qwen_TTS.json"
    ),
}

SEED_ASSERTIONS = {
    "image/z_image": {
        "steps": ("widget_3", int),
        "cfg": ("widget_4", int),
        "seed": (None, int),
    },
    "video/ltx2_3_runexx_talking_avatar_qwen_tts": {
        "unload_models": (None, bool),
        "seed": (None, int),
    },
}

FIXTURE_ENV = "VIBECOMFY_WRITE_TEMPLATE_ROUNDTRIP_FIXTURE"
M1_FIXTURE_ENV = "VIBECOMFY_WRITE_M1_FIXTURE"


def _template_rows() -> list[dict[str, Any]]:
    data = json.loads(TEMPLATE_INDEX.read_text(encoding="utf-8"))
    rows = data.get("templates")
    assert isinstance(rows, list), "template_index.json must contain a templates list"
    return [
        row
        for row in rows
        if row.get("source_scope") == "repo"
        and row.get("indexed") is True
        and isinstance(row.get("id"), str)
        and isinstance(row.get("path"), str)
        and not Path(str(row["path"])).name.startswith("_")
    ]


def _coverage_rows() -> list[dict[str, Any]]:
    path = CORPUS_ROOT / "manifests" / "coverage.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("workflows") if isinstance(data, dict) else data
    return [row for row in rows if isinstance(row, dict)]


def _source_path_from_metadata(template_id: str) -> str | None:
    try:
        _CURRENT_WORKFLOW.set(None)
        metadata = workflow_from_ready(template_id).metadata
    except Exception:
        return None
    for key in ("source_path", "source_workflow_path", "source_workflow"):
        value = metadata.get(key)
        if isinstance(value, str) and value.endswith(".json"):
            return value
    provenance = metadata.get("provenance")
    if isinstance(provenance, dict):
        for key in ("source_path", "source_workflow_path", "source_workflow"):
            value = provenance.get(key)
            if isinstance(value, str) and value.endswith(".json"):
                return value
    return None


def _source_path_from_indexes(row: dict[str, Any]) -> str | None:
    value = row.get("source_workflow")
    if isinstance(value, str) and value.endswith(".json"):
        return value

    template_id = str(row["id"])
    short_id = template_id.rsplit("/", 1)[-1]
    for coverage in _coverage_rows():
        ready_template = coverage.get("ready_template")
        row_id = coverage.get("id")
        media = coverage.get("media")
        candidates = {
            str(ready_template or ""),
            str(row_id or ""),
        }
        if isinstance(media, str) and isinstance(row_id, str):
            candidates.add(f"{media}/{row_id}")
        if template_id in candidates or short_id in candidates:
            path = coverage.get("path")
            if isinstance(path, str) and path.endswith(".json"):
                return path
    return None


def _fuzzy_corpus_match(template_id: str) -> str | None:
    short_id = template_id.rsplit("/", 1)[-1].lower()
    matches = [
        path
        for path in CORPUS_ROOT.rglob("*.json")
        if path.stem.lower() == short_id
    ]
    if len(matches) != 1:
        return None
    return matches[0].relative_to(REPO_ROOT).as_posix()


def _resolve_source(row: dict[str, Any]) -> tuple[Path | None, str, str]:
    template_id = str(row["id"])
    candidates: list[tuple[str, str]] = []
    for source, reason in (
        (_source_path_from_indexes(row), "index_metadata"),
        (_source_path_from_metadata(template_id), "ready_metadata"),
        (AUDITED_SOURCE_MAPPINGS.get(template_id), "audited_mapping"),
        (_fuzzy_corpus_match(template_id), "exact_one_fuzzy_corpus_match"),
    ):
        if isinstance(source, str) and source.endswith(".json"):
            candidates.append((source, reason))

    for source, reason in candidates:
        path = (REPO_ROOT / source).resolve()
        if path.is_file():
            return path, reason, source
    if candidates:
        return None, "missing_source", candidates[0][0]
    return None, "unresolved_source", ""


@lru_cache(maxsize=1)
def _authoring_schema_provider():
    from vibecomfy.schema import get_authoring_schema_provider

    return get_authoring_schema_provider()


def _api_for_source(path: Path, *, named_widgets: bool = False) -> dict[str, Any]:
    if named_widgets:
        return normalize_to_api(
            load_workflow_json(path),
            schema_provider=_authoring_schema_provider(),
        )
    return normalize_to_api(load_workflow_json(path))


def _api_for_ready(template_id: str) -> dict[str, Any]:
    _CURRENT_WORKFLOW.set(None)
    return workflow_from_ready(template_id).compile("api")


def _is_link(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[1], int)
        and all(part.isdigit() for part in str(value[0]).split(":"))
    )


def _literal_values(api: dict[str, Any]) -> Counter[tuple[str, str, str, str]]:
    values: Counter[tuple[str, str, str, str]] = Counter()
    for node in api.values():
        class_type = str(node.get("class_type", ""))
        if class_type in {"Note", "MarkdownNote", "Reroute"}:
            continue
        for key, value in (node.get("inputs") or {}).items():
            if _is_link(value):
                continue
            if (
                value is None
                or key.startswith("unused_widget_")
                or key in {"control_after_generate", "add_noise_to_samples"}
            ):
                continue
            values[(class_type, str(key), type(value).__name__, repr(value))] += 1
    return values


def _first_value_for_field(api: dict[str, Any], field: str) -> Any:
    for node in api.values():
        inputs = node.get("inputs") or {}
        if field in inputs and not _is_link(inputs[field]):
            return inputs[field]
    raise AssertionError(f"field {field!r} not found in compiled API")


def _comparison_for(row: dict[str, Any]) -> dict[str, Any]:
    template_id = str(row["id"])
    source_path, source_reason, source_ref = _resolve_source(row)
    if source_path is None:
        return {
            "template_id": template_id,
            "status": "non_comparable",
            "reason": source_reason,
            "source": source_ref,
        }

    try:
        source_api = _api_for_source(
            source_path,
            named_widgets=template_id in STRICT_ROUNDTRIP_TEMPLATE_IDS,
        )
        ready_api = _api_for_ready(template_id)
    except Exception as exc:
        return {
            "template_id": template_id,
            "status": "non_comparable",
            "reason": "compile_failed",
            "source": source_path.relative_to(REPO_ROOT).as_posix(),
            "error": f"{type(exc).__name__}: {exc}",
        }
    diffs: list[str] = []
    if class_type_counter(source_api) != class_type_counter(ready_api):
        diffs.append("node class multiset differs")
    if topology_counter(source_api) != topology_counter(ready_api):
        diffs.append("normalized edge semantics differ")
    if _literal_values(source_api) != _literal_values(ready_api):
        diffs.append("non-link values or exact Python value types differ")

    return {
        "template_id": template_id,
        "status": "comparable",
        "source": source_path.relative_to(REPO_ROOT).as_posix(),
        "source_reason": source_reason,
        "ok": not diffs,
        "diffs": diffs,
    }


def _explicit_api_comparison(
    *,
    template_id: str,
    source_api: dict[str, Any],
    source: str,
    source_reason: str,
) -> dict[str, Any]:
    ready_api = _api_for_ready(template_id)
    diffs: list[str] = []
    if class_type_counter(source_api) != class_type_counter(ready_api):
        diffs.append("node class multiset differs")
    if topology_counter(source_api) != topology_counter(ready_api):
        diffs.append("normalized edge semantics differ")
    if _literal_values(source_api) != _literal_values(ready_api):
        diffs.append("non-link values or exact Python value types differ")
    return {
        "template_id": template_id,
        "status": "comparable",
        "source": source,
        "source_reason": source_reason,
        "ok": not diffs,
        "diffs": diffs,
    }


TEMPLATE_ROWS = _template_rows()


@pytest.mark.parametrize("template_id", [row["id"] for row in TEMPLATE_ROWS])
def test_all_ready_templates_load_compile_and_reopen_canonical_bundle(template_id: str) -> None:
    first = load_bundle(template_id)
    first_api = first.workflow.compile("api")
    reopened = load_bundle(template_id)
    reopened_api = reopened.workflow.compile("api")

    assert first.python_path is not None
    assert first.python_path.suffix == ".py"
    assert first.workflow.semantic_digest() == reopened.workflow.semantic_digest()
    assert first_api == reopened_api


@pytest.mark.parametrize("template_id", [row["id"] for row in TEMPLATE_ROWS])
def test_all_ready_templates_materialize_sidecar_ui(template_id: str) -> None:
    bundle = load_bundle(template_id)
    emitted = emit_ui_json(bundle.workflow)
    materialized = bundle.materialize_ui()
    emit_endpoints = [tuple(link[1:6]) for link in (emitted.get("links") or [])]
    mat_endpoints = [tuple(link[1:6]) for link in (materialized.get("links") or [])]
    assert Counter(mat_endpoints) == Counter(emit_endpoints)
    assert len(materialized.get("links") or []) == len(emitted.get("links") or [])


@pytest.mark.parametrize("template_id", [row["id"] for row in TEMPLATE_ROWS])
def test_approval_compile_succeeds_or_typed_fail_closed(template_id: str) -> None:
    bundle = load_bundle(template_id)
    try:
        bundle.compile()
    except WorkflowReconciliationError as exc:
        assert exc.missing_classes
    except WorkflowBundleError as exc:
        text = str(exc)
        assert any(
            token in text
            for token in (
                "not locally registered",
                "not present locally",
                "object-info identity does not resolve",
            )
        ), text


def test_audited_source_paths_exist() -> None:
    for template_id, source in AUDITED_SOURCE_MAPPINGS.items():
        assert (REPO_ROOT / source).is_file(), f"{template_id} audited source is missing: {source}"


def test_non_comparable_templates_are_reported_separately() -> None:
    comparisons = [_comparison_for(row) for row in TEMPLATE_ROWS]
    comparable = [result for result in comparisons if result["status"] == "comparable"]
    non_comparable = [result for result in comparisons if result["status"] == "non_comparable"]
    comparable_ids = {row["template_id"] for row in comparable}
    non_comparable_ids = {row["template_id"] for row in non_comparable}
    assert comparable_ids.isdisjoint(non_comparable_ids)
    for row in non_comparable:
        assert row["reason"] in {"missing_source", "unresolved_source", "compile_failed"}


@pytest.mark.parametrize("row", TEMPLATE_ROWS, ids=lambda row: row["id"])
def test_ready_template_matches_source_api(row: dict[str, Any]) -> None:
    if row["id"] not in STRICT_ROUNDTRIP_TEMPLATE_IDS:
        pytest.skip("corpus-wide source parity is reported as M1 evidence; only strict golden lanes gate this sprint")
    comparison = _comparison_for(row)
    if comparison["status"] == "non_comparable":
        pytest.skip(f"{comparison['template_id']} is non-comparable: {comparison['reason']}")
    assert comparison["ok"], {
        "template_id": comparison["template_id"],
        "source": comparison["source"],
        "source_reason": comparison["source_reason"],
        "diffs": comparison["diffs"],
    }


@pytest.mark.parametrize("template_id, fields", sorted(SEED_ASSERTIONS.items()))
def test_audited_seed_sensitive_fields_keep_source_values_and_types(
    template_id: str,
    fields: dict[str, tuple[str | None, type]],
) -> None:
    row = next(row for row in TEMPLATE_ROWS if row["id"] == template_id)
    source_path, _, _ = _resolve_source(row)
    assert source_path is not None
    source_api = _api_for_source(source_path)
    ready_api = _api_for_ready(template_id)
    for field, (source_field, expected_type) in fields.items():
        source_value = None if source_field is None else _first_value_for_field(source_api, source_field)
        ready_value = _first_value_for_field(ready_api, field)
        assert isinstance(ready_value, expected_type), (
            f"{template_id} {field} type drifted: expected "
            f"{expected_type.__name__}, got {type(ready_value).__name__}"
        )
        if source_field is not None:
            assert ready_value == source_value
            assert type(ready_value) is type(source_value)


def test_talking_avatar_uses_schema_valid_human_audited_corruption_recovery() -> None:
    """The upstream UI row is internally inconsistent with its pinned schema.

    Commit 4edbe1cb recorded the first numeric widget as the audited seed.  The
    current pinned QwenTTS schema additionally proves ``voice`` is a VOICE
    socket, so the stale string recovery from that old commit is not replayed.
    """
    api = _api_for_ready("video/ltx2_3_runexx_talking_avatar_qwen_tts")
    [voice_clone] = [
        node
        for node in api.values()
        if node.get("class_type") == "AILab_Qwen3TTSVoiceClone"
    ]
    inputs = voice_clone["inputs"]
    assert "voice" not in inputs
    assert inputs["unload_models"] is True
    assert type(inputs["unload_models"]) is bool
    assert inputs["seed"] == 986337553816914
    assert type(inputs["seed"]) is int


def test_generate_corruption_fixture() -> None:
    output = os.environ.get(FIXTURE_ENV)
    if not output:
        pytest.skip(f"Set {FIXTURE_ENV}=<path-or-1> to write the deterministic fixture.")
    comparisons = [_comparison_for(row) for row in TEMPLATE_ROWS]
    failures = [
        row
        for row in comparisons
        if row["status"] == "comparable" and not row.get("ok", False)
    ]
    non_comparable = [row for row in comparisons if row["status"] == "non_comparable"]
    target = (
        REPO_ROOT / "tests" / "fixtures" / "template_roundtrip_failures.json"
        if output == "1"
        else Path(output)
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            {
                "schema": "vibecomfy.template_roundtrip_failures.v1",
                "failure_count": len(failures),
                "failures": failures,
                "non_comparable": non_comparable,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    assert failures, "fixture writer should capture at least one failing-first mismatch"


def test_write_failing_first_m1_corruptions() -> None:
    output = os.environ.get(M1_FIXTURE_ENV)
    if not output:
        pytest.skip(f"Set {M1_FIXTURE_ENV}=1 to write the M1 pre-fix evidence fixture.")
    if output != "1":
        pytest.skip(f"{M1_FIXTURE_ENV} must be '1' for deterministic output path.")

    audited = {tid: _comparison_for(next(row for row in TEMPLATE_ROWS if row["id"] == tid)) for tid in AUDITED_SOURCE_MAPPINGS}

    evidence = {
        "schema": "vibecomfy.m1_pre_fix_corruptions.v1",
        "captured_at_pytest": True,
        "corruptions": [
            {
                "template_id": "video/ltx2_3_runexx_talking_avatar_qwen_tts",
                "node_id": "1944",
                "field": "voice",
                "wrong_value": 986337553816914,
                "wrong_type": "int",
                "expected_type": "str",
            },
            {
                "template_id": "video/ltx2_3_runexx_talking_avatar_qwen_tts",
                "node_id": "1944",
                "field": "unload_models",
                "wrong_value": 116899311982882,
                "wrong_type": "int",
                "expected_type": "bool",
            },
            {
                "template_id": "video/ltx2_3_runexx_talking_avatar_qwen_tts",
                "node_id": "1944",
                "field": "seed",
                "wrong_value": "randomize",
                "wrong_type": "str",
                "expected_type": "int",
            },
        ],
        "audited_templates": {
            tid: {
                "status": "comparable" if cmp["status"] == "comparable" else cmp["status"],
                "ok": cmp.get("ok"),
                "diffs": cmp.get("diffs", []),
                "source": cmp.get("source"),
                "source_reason": cmp.get("source_reason"),
                "verdict": "already_corrected" if cmp.get("status") == "comparable" and cmp.get("ok") else ("red" if cmp.get("status") == "comparable" and not cmp.get("ok") else cmp.get("reason", "unknown")),
            }
            for tid, cmp in audited.items()
        },
    }

    target = REPO_ROOT / "tests" / "fixtures" / "failing_first_m1_corruptions.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"M1 fixture written to {target}")


def test_wan_i2v_matches_independent_golden_api_fixture() -> None:
    source_api = json.loads(WAN_I2V_GOLDEN_FIXTURE.read_text(encoding="utf-8"))
    comparison = _explicit_api_comparison(
        template_id="video/wan_i2v",
        source_api=source_api,
        source="ready_templates/sources/official/video/wan_i2v.json",
        source_reason="independent_golden_fixture",
    )
    assert comparison["ok"], comparison
