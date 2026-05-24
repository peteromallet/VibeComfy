from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest

from vibecomfy import load_workflow_any
from vibecomfy.porting.convert import port_convert_workflow
from vibecomfy.porting.parity import class_type_counter, topology_counter
from vibecomfy.porting.workbench import load_port_source
from vibecomfy.schema import get_authoring_schema_provider


ROUNDTRIP_CASES = {
    "audio/qwen3_tts_custom_voice": "ready_templates/audio/qwen3_tts_custom_voice.py",
    "audio/qwen3_tts_voice_clone": "ready_templates/audio/qwen3_tts_voice_clone.py",
    "audio/qwen3_tts_voice_design": "ready_templates/audio/qwen3_tts_voice_design.py",
    "image/flux2_klein_9b_t2i": "ready_templates/image/flux2_klein_9b_t2i.py",
    "video/basic_video_enhance": "ready_templates/video/basic_video_enhance.py",
}


UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


def _without_uuid_classes(counter: Counter[str]) -> Counter[str]:
    return Counter({key: value for key, value in counter.items() if not UUID_RE.fullmatch(key)})


def _without_uuid_topology(counter: Counter[tuple[str, str, str, int]]) -> Counter[tuple[str, str, str, int]]:
    return Counter(
        {
            key: value
            for key, value in counter.items()
            if not UUID_RE.fullmatch(key[0]) and not UUID_RE.fullmatch(key[2])
        }
    )


def _converted_workflow(tmp_path: Path, ready_id: str, source: str):
    schema_provider = get_authoring_schema_provider()
    loaded = load_port_source(source, schema_provider=schema_provider)
    result = port_convert_workflow(
        loaded.workflow,
        source_path=loaded.source_path,
        schema_provider=schema_provider,
        raw_workflow=loaded.raw_workflow,
    )
    out_path = tmp_path / (ready_id.replace("/", "__") + ".py")
    out_path.write_text(result.text, encoding="utf-8")
    return loaded.workflow, load_workflow_any(str(out_path))


@pytest.mark.parametrize("ready_id,source", ROUNDTRIP_CASES.items(), ids=ROUNDTRIP_CASES.keys())
def test_port_convert_roundtrip_preserves_structural_contract(tmp_path: Path, ready_id: str, source: str) -> None:
    source_wf, emitted_wf = _converted_workflow(tmp_path, ready_id, source)
    source_api = source_wf.compile("api")
    emitted_api = emitted_wf.compile("api")

    source_classes = class_type_counter(source_api)
    emitted_classes = class_type_counter(emitted_api)
    if source_classes != emitted_classes:
        # Materialized subgraphs replace UUID class nodes with their internal
        # Python function bodies; compare the non-UUID surface explicitly.
        assert any(UUID_RE.fullmatch(class_type) for class_type in source_classes)
        assert _without_uuid_classes(source_classes) <= _without_uuid_classes(emitted_classes)
    else:
        assert source_classes == emitted_classes

    source_edges = topology_counter(source_api)
    emitted_edges = topology_counter(emitted_api)
    if source_edges != emitted_edges:
        # Helper/UI stripping, UUID subgraph expansion, and broadcast ordering
        # are documented roundtrip caveats. Non-UUID edges from the source must
        # still be preserved.
        assert _without_uuid_topology(source_edges) <= _without_uuid_topology(emitted_edges)
    else:
        assert source_edges == emitted_edges

    source_input_keys = set(source_wf.inputs)
    emitted_input_keys = set(emitted_wf.inputs)
    assert source_input_keys <= emitted_input_keys
