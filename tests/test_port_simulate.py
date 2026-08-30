from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from vibecomfy.porting import simulate

from vibecomfy.schema.provider import InputSpec, NodeSchema

def _source(body: str = "    return VibeWorkflow(id='case', source=WorkflowSource(id='case'))") -> str:
    return (
        "# vibecomfy: generated\n"
        "from __future__ import annotations\n"
        "from vibecomfy.workflow import VibeWorkflow, WorkflowSource\n\n"
        "def build() -> VibeWorkflow:\n"
        f"{body}\n"
    )


def _corpus(path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        simulate,
        "build_corpus_snapshot",
        lambda _root: SimpleNamespace(
            templates_list=[{"id": "image/case", "path": str(path), "marker": "generated"}]
        ),
    )
    monkeypatch.setattr(simulate, "get_schema_provider", lambda _mode: None)


def test_real_generated_template_is_admitted_and_executes_original_and_transform_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = Path("ready_templates/image/basic_image_upscale.py").read_text(encoding="utf-8")
    path = tmp_path / "basic_image_upscale.py"
    path.write_text(source + "\n# _set_id_map(\n", encoding="utf-8")
    _corpus(path, monkeypatch)
    calls: list[str] = []
    original = simulate._run_artifact_worker

    def counted(path: Path, *, logical_path: Path) -> dict[str, object]:
        calls.append(path.name)
        return original(path, logical_path=logical_path)

    monkeypatch.setattr(simulate, "_run_artifact_worker", counted)
    result = simulate.simulate_rule("drop_set_id_map=true", ["image/case"])

    assert result.status == "ok"
    assert result.parity_preserved == 1
    assert result.unsupported == 0
    assert len(calls) == 2
    assert result.schema_snapshot_digest


@pytest.mark.parametrize(
    ("source", "code"),
    [
        (_source().replace("# vibecomfy: generated\n", "# vibecomfy: generated\nimport os\n"), "forbidden_environment"),
        (_source().replace("# vibecomfy: generated\n", "# vibecomfy: generated\nimport pathlib\n"), "forbidden_source_read"),
        (_source().replace("# vibecomfy: generated\n", "# vibecomfy: generated\nimport subprocess\n"), "forbidden_process"),
        (_source().replace("# vibecomfy: generated\n", "# vibecomfy: generated\nimport socket\n"), "forbidden_network"),
        (_source().replace("# vibecomfy: generated\n", "# vibecomfy: generated\nimport sqlite3\n"), "forbidden_database"),
        (_source().replace("# vibecomfy: generated\n", "# vibecomfy: generated\nimport random\n"), "forbidden_entropy"),
        (_source().replace("# vibecomfy: generated\n", "# vibecomfy: generated\nimport time\n"), "forbidden_time"),
        (_source().replace("# vibecomfy: generated\n", "# vibecomfy: generated\nimport sys\n"), "forbidden_protocol_fd"),
        (_source().replace("# vibecomfy: generated\n", "# vibecomfy: generated\nfrom vibecomfy.schema import get_schema_provider\n"), "arbitrary_provider_import"),
        (_source("    return eval('1')"), "forbidden_dynamic_execution"),
        (_source("    return getattr(VibeWorkflow, 'x')"), "forbidden_introspection"),
        (_source("    return open(__file__).read()"), "forbidden_source_read"),
    ],
)
def test_admission_refuses_each_unsafe_capability(source: str, code: str) -> None:
    admission = simulate.admit_template_source(source)
    assert admission.status == "unsupported"
    assert admission.admitted is False
    assert admission.reason is not None
    assert admission.reason["code"] == code
    assert set(admission.reason) == {"code", "message", "line", "column"}


def test_unsupported_is_structured_and_not_parity_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "unsafe.py"
    path.write_text(
        "# vibecomfy: generated\n"
        "from __future__ import annotations\n"
        "import os\n"
        "from vibecomfy.workflow import VibeWorkflow, WorkflowSource\n\n"
        "def build() -> VibeWorkflow:\n"
        "    return VibeWorkflow(id='case', source=WorkflowSource(id='case'))\n",
        encoding="utf-8",
    )
    _corpus(path, monkeypatch)

    result = simulate.simulate_rule("drop_set_id_map=true", ["image/case"])

    assert result.status == "unsupported"
    assert result.unsupported == 1
    assert result.parity_broken == 0
    assert result.parity_preserved == 0
    assert result.per_template[0]["status"] == "unsupported"
    assert result.per_template[0]["parity_ok"] is None
    assert result.per_template[0]["unsupported"]["reason"]["code"] == "forbidden_environment"


def test_logical_file_is_preserved_by_worker(tmp_path: Path) -> None:
    path = tmp_path / "logical.py"
    path.write_text(
        "# vibecomfy: generated\n"
        "from vibecomfy.workflow import VibeWorkflow, WorkflowSource\n\n"
        "def build():\n"
        "    return VibeWorkflow(id='logical', source=WorkflowSource(id='logical', path=__file__))\n",
        encoding="utf-8",
    )
    result = simulate._run_artifact_worker(path, logical_path=Path("/logical/template.py"))
    assert result["envelope"]["source"]["path"] == "/logical/template.py"

def test_protocol_payload_is_bounded() -> None:
    read_fd, write_fd = os.pipe()
    try:
        simulate._emit_worker_payload({"ok": True, "data": "x" * simulate._PROTOCOL_LIMIT}, write_fd)
        os.close(write_fd)
        write_fd = -1
        payload = os.fdopen(read_fd, "rb").read()
        read_fd = -1
        assert len(payload) < simulate._PROTOCOL_LIMIT
        assert json.loads(payload)["ok"] is False
    finally:
        if write_fd >= 0:
            os.close(write_fd)
        if read_fd >= 0:
            os.close(read_fd)


def test_schema_snapshot_is_frozen_before_worker_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "schema.py"
    path.write_text(_source("    return VibeWorkflow(id='case', source=WorkflowSource(id='case'))"), encoding="utf-8")
    _corpus(path, monkeypatch)
    class Provider:
        calls = 0
        def schemas(self):
            self.calls += 1
            return {}
        def get_schema(self, _class_type):
            raise AssertionError("worker/provider lookup must not occur")
    provider = Provider()
    result = simulate.simulate_rule("drop_set_id_map=false", ["image/case"], schema_provider=provider)
    assert result.status == "ok"
    assert provider.calls == 1
    assert result.schema_snapshot_digest


def test_schema_snapshot_serialization_freezes_provider_drift() -> None:
    class Provider:
        version = 1

        def schemas(self):
            return {
                "Demo": NodeSchema(
                    class_type="Demo",
                    pack="test",
                    inputs={"value": InputSpec(type="INT", default=self.version)},
                    outputs=[],
                )
            }

    provider = Provider()
    payload = simulate._freeze_schema_snapshot(provider, {"Demo"})
    provider.version = 2
    frozen = simulate.schema_snapshot_provider_from_payload(payload)
    assert frozen.get_schema("Demo").inputs["value"].default == 1
