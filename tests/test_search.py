from __future__ import annotations

import os
import json
import subprocess
import sys
from pathlib import Path

import pytest

from vibecomfy.search import SearchBootstrapError, ensure_indexes, search_entries
from vibecomfy.search.index import build_search_corpus
from vibecomfy.search.index import SearchEntry


REPO_ROOT = Path(__file__).resolve().parents[1]


def _cli_env() -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(REPO_ROOT) if not existing else f"{REPO_ROOT}{os.pathsep}{existing}"
    return env


def test_search_task_alias_hits_expected_entry() -> None:
    entries = [
        SearchEntry(
            class_type="WanImageToVideoSampler",
            pack="wan-pack",
            description="image to video generation node",
            tags=("video",),
            tasks=("i2v",),
            source="curated",
        ),
        SearchEntry(
            class_type="AudioReactiveNode",
            pack="audio-pack",
            description="audio reactive animation",
            tags=("audio",),
            tasks=("audio_reactive",),
            source="curated",
        ),
    ]

    results = search_entries(entries, "wan", task="i2v", limit=10)

    assert [result.entry.class_type for result in results] == ["WanImageToVideoSampler"]
    assert results[0].score > 0
    assert "alias" in results[0].reasons


def test_exact_class_type_wins_over_partial_description_match() -> None:
    entries = [
        SearchEntry(
            class_type="WanVideoSamplerXL",
            description="WanVideoSampler helper",
            source="curated",
        ),
        SearchEntry(
            class_type="WanVideoSampler",
            description="generic node",
            source="curated",
        ),
    ]

    results = search_entries(entries, "WanVideoSampler", limit=10)

    assert [result.entry.class_type for result in results] == ["WanVideoSampler", "WanVideoSamplerXL"]
    assert results[0].score > results[1].score


def test_pack_match_ranks_above_description_only_match() -> None:
    entries = [
        SearchEntry(
            class_type="DescriptionOnlyNode",
            description="wan capable processor",
            source="curated",
        ),
        SearchEntry(
            class_type="PackNode",
            pack="wan",
            description="generic processor",
            source="curated",
        ),
    ]

    results = search_entries(entries, "wan", limit=10)

    assert [result.entry.class_type for result in results] == ["PackNode", "DescriptionOnlyNode"]
    assert "pack" in results[0].reasons
    assert "description" in results[1].reasons


def test_ensure_indexes_raises_without_index_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SearchBootstrapError, match="vibecomfy sources sync"):
        ensure_indexes(auto_sync=False)


def test_search_cli_surfaces_bootstrap_error_from_empty_cwd(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "vibecomfy.cli", "search", "wan"],
        cwd=tmp_path,
        env=_cli_env(),
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "vibecomfy sources sync" in result.stdout


def test_search_cli_smoke_returns_wan_i2v_hits_after_sources_sync() -> None:
    sync = subprocess.run(
        [sys.executable, "-m", "vibecomfy.cli", "sources", "sync"],
        cwd=REPO_ROOT,
        env=_cli_env(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert sync.returncode == 0, sync.stderr or sync.stdout

    result = subprocess.run(
        [sys.executable, "-m", "vibecomfy.cli", "search", "wan", "--task", "i2v"],
        cwd=REPO_ROOT,
        env=_cli_env(),
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    rows = [line for line in result.stdout.splitlines() if line.strip()]
    assert rows[0] == "id\tclass_type\tpack\tscore\tsource"
    assert len(rows) >= 2


def test_search_cli_json_is_agent_readable_after_sources_sync() -> None:
    sync = subprocess.run(
        [sys.executable, "-m", "vibecomfy.cli", "sources", "sync"],
        cwd=REPO_ROOT,
        env=_cli_env(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert sync.returncode == 0, sync.stderr or sync.stdout

    result = subprocess.run(
        [sys.executable, "-m", "vibecomfy.cli", "search", "ltx", "--task", "i2v", "--json"],
        cwd=REPO_ROOT,
        env=_cli_env(),
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["query"] == "ltx"
    assert payload["task"] == "i2v"
    assert payload["results"]
    assert {"id", "score", "reasons", "entry"} <= set(payload["results"][0])


def test_local_adapt_alias_discovery_finds_vace_template_with_parseable_source() -> None:
    entries = build_search_corpus()

    results = search_entries(entries, "VACE identity travel from a reference image", task="i2v", limit=5)

    assert results
    top = results[0]
    assert top.entry.class_type == "video/wanvideo_wrapper_13b_vace"
    assert top.entry.template_id == "video/wanvideo_wrapper_13b_vace"
    assert top.entry.path == "ready_templates/video/wanvideo_wrapper_13b_vace.py"
    assert top.entry.source_workflow_path == "ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan13b_vace.json"
    assert top.entry.source_workflow_available is True
    assert top.entry.source_workflow_parseable is True
    assert "vace" in top.entry.adapt_pattern_keys
    assert "adapt_pattern" in top.reasons
    assert "graph_backed" in top.reasons


def test_local_adapt_alias_discovery_prefers_graph_backed_lora_template() -> None:
    entries = build_search_corpus()

    results = search_entries(entries, "LoRA chaining with IC-LoRA control guide", task="i2v", limit=6)

    assert results
    top = results[0]
    assert "lora_chain" in top.entry.adapt_pattern_keys
    assert top.entry.source_workflow_path
    assert top.entry.source_workflow_path.endswith(".json")
    assert top.entry.source_workflow_available is True
    assert top.entry.source_workflow_parseable is True
    assert top.entry.path
    assert top.entry.path.startswith("ready_templates/video/")
    assert top.entry.path.endswith(".py")
    assert "graph_backed" in top.reasons


def test_search_cli_reads_object_info_cache(tmp_path: Path) -> None:
    cache = tmp_path / "object_info.json"
    cache.write_text(
        json.dumps(
            {
                "LTXRuntimeScheduler": {
                    "input": {"required": {"steps": ["INT", {"default": 20}]}},
                    "output": ["SIGMAS"],
                    "category": "runtime/ltx",
                }
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "vibecomfy.cli",
            "search",
            "LTXRuntimeScheduler",
            "--object-info-cache",
            str(cache),
            "--limit",
            "50",
            "--json",
        ],
        cwd=REPO_ROOT,
        env=_cli_env(),
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    class_types = [item["entry"]["class_type"] for item in payload["results"]]
    assert "LTXRuntimeScheduler" in class_types


def test_build_search_corpus_warns_when_explicit_schema_provider_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "node_index.json").write_text("[]", encoding="utf-8")
    (tmp_path / "workflow_index.json").write_text("[]", encoding="utf-8")
    (tmp_path / "external_workflow_index.json").write_text("[]", encoding="utf-8")
    coverage = tmp_path / "ready_templates/sources" / "manifests" / "coverage.json"
    coverage.parent.mkdir(parents=True)
    coverage.write_text('{"workflows": []}', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    warnings = []

    entries = build_search_corpus(schema_provider=FailingSchemaProvider(), warnings=warnings)

    assert entries == []
    assert len(warnings) == 1
    assert warnings[0].source == "object_info"
    assert "object_info schema discovery failed" in warnings[0].message
    assert "RuntimeError: boom" in warnings[0].message


def test_build_search_corpus_surfaces_only_ready_template_python_for_workflows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "node_index.json").write_text("[]", encoding="utf-8")
    (tmp_path / "template_index.json").write_text(
        json.dumps(
            {
                "templates": [
                    {
                        "id": "video/ltx2_3_t2v",
                        "path": "ready_templates/video/ltx2_3_t2v.py",
                        "source_workflow": "ready_templates/sources/custom_nodes/ltxvideo/ltx2_3.json",
                        "capability": "video",
                        "coverage_tier": "required",
                        "readiness_class": "ready",
                        "public_inputs": [{"name": "prompt"}, {"name": "seed"}],
                        "public_outputs": [{"name": "video"}],
                        "custom_nodes": ["LTXVLoader"],
                        "model_count": 2,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "workflow_index.json").write_text(
        json.dumps(
            [
                {
                    "id": "image/json_only_template",
                    "path": "ready_templates/sources/custom_nodes/json_only_template.json",
                    "source_workflow": "ready_templates/sources/custom_nodes/json_only_template.json",
                    "capability": "image",
                },
                {
                    "id": "wan_official_i2v",
                    "path": "ready_templates/sources/official/video/wan_i2v.json",
                    "media_type": "video",
                    "source": "Comfy-Org/workflow_templates",
                },
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "external_workflow_index.json").write_text(
        json.dumps(
            [
                {
                    "id": "flux_depth_control",
                    "path": "ready_templates/sources/custom_nodes/flux/depth_control.json",
                    "media_type": "image",
                    "package": "flux-pack",
                    "public_inputs": [{"name": "depth"}],
                    "public_outputs": [{"name": "image"}],
                    "custom_nodes": ["FluxDepth"],
                    "model_count": 1,
                }
            ]
        ),
        encoding="utf-8",
    )
    coverage = tmp_path / "ready_templates/sources/manifests/coverage.json"
    coverage.parent.mkdir(parents=True)
    coverage.write_text(
        json.dumps(
            {
                "workflows": [
                    {
                        "id": "coverage_json_only",
                        "path": "ready_templates/sources/official/video/coverage_json_only.json",
                        "task": "text_to_video",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    entries = build_search_corpus()
    by_id = {entry.class_type: entry for entry in entries}

    ready = by_id["video/ltx2_3_t2v"]
    assert ready.source == "ready_template"
    assert ready.path == "ready_templates/video/ltx2_3_t2v.py"
    assert "converted source workflow ltx2_3" in ready.description
    assert "prompt" in ready.tags
    assert "LTXVLoader" in ready.tags

    assert "image/json_only_template" not in by_id
    assert "wan_official_i2v" not in by_id
    assert "flux_depth_control" not in by_id
    assert "coverage_json_only" not in by_id

    workflow_entries = [
        entry
        for entry in entries
        if entry.source in {"ready_template", "source_workflow", "external_workflow", "curated", "custom_node_examples"}
    ]
    assert workflow_entries
    assert all(entry.path is None or entry.path.endswith(".py") for entry in workflow_entries)

    results = search_entries(entries, "ltx2 3", limit=5)
    assert results[0].entry.class_type == "video/ltx2_3_t2v"
    assert results[0].entry.path == "ready_templates/video/ltx2_3_t2v.py"


class FailingSchemaProvider:
    def schemas(self):
        raise RuntimeError("boom")
