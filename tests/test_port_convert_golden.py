"""Golden tests for post-F ``port convert`` output.

Snapshots in ``tests/snapshots/port_convert/*.py.expected`` are intentionally
byte-for-byte. To update them, make the emitter change deliberately, inspect the
diff, then regenerate the affected files with the same helper path this test
uses. Do not accept snapshot churn from unrelated template or formatter edits.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vibecomfy.porting.convert import port_convert_workflow
from vibecomfy.porting.workbench import load_port_source
from vibecomfy.schema import get_authoring_schema_provider


SNAPSHOT_ROOT = Path("tests/snapshots/port_convert")

GOLDEN_CASES = {
    "image/z_image": "workflow_corpus/official/image/z_image.json",
    "image/qwen_image_2512": "workflow_corpus/official/image/qwen_image_2512.json",
    "video/wan_t2v": "workflow_corpus/official/video/wan_t2v.json",
    "video/wan_i2v": "workflow_corpus/official/video/wan_i2v.json",
    "image/flux2_klein_4b_t2i": "workflow_corpus/official/image/flux2_klein_4b_t2i.json",
    "audio/ace_step_1_5_t2a_song": "workflow_corpus/official/audio/ace_step_1_5_t2a_song.json",
}


def _snapshot_name(ready_id: str) -> str:
    return ready_id.replace("/", "__") + ".py.expected"


def _port_convert_text(ready_id: str, source: str) -> str:
    schema_provider = get_authoring_schema_provider()
    loaded = load_port_source(source, schema_provider=schema_provider)
    result = port_convert_workflow(
        loaded.workflow,
        ready_id=ready_id,
        source_path=loaded.source_path,
        schema_provider=schema_provider,
        raw_workflow=loaded.raw_workflow,
    )
    return result.text


@pytest.mark.parametrize("ready_id,source", GOLDEN_CASES.items(), ids=GOLDEN_CASES.keys())
def test_port_convert_output_matches_post_f_snapshot(ready_id: str, source: str) -> None:
    expected = (SNAPSHOT_ROOT / _snapshot_name(ready_id)).read_text(encoding="utf-8")
    assert _port_convert_text(ready_id, source) == expected
