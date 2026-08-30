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


@pytest.mark.parametrize(
    ("module", "name"),
    [
        ("vibecomfy.templates", "Path"),
        ("vibecomfy.templates", "inspect"),
        ("vibecomfy.templates", "json"),
        ("vibecomfy.templates", "find_repo_root"),
        ("vibecomfy.workflow", "Path"),
        ("vibecomfy.nodes.core", "_current_workflow_or_raise"),
        ("vibecomfy.patches.resolution", "Path"),
    ],
)
def test_admission_refuses_reexported_or_private_imports(module: str, name: str) -> None:
    source = _source().replace(
        "from vibecomfy.workflow import VibeWorkflow, WorkflowSource",
        f"from {module} import {name}\nfrom vibecomfy.workflow import VibeWorkflow, WorkflowSource",
    )
    admission = simulate.admit_template_source(source)
    assert admission.status == "unsupported"
    assert admission.reason is not None
    assert admission.reason["code"] == "forbidden_import_name"


@pytest.mark.parametrize(
    "body",
    [
        "    Path('/tmp/grok-path-write').write_text('hit')\n    return VibeWorkflow(id='case', source=WorkflowSource(id='case'))",
        "    source_length = len(Path(__file__).read_text())\n    return VibeWorkflow(id='case', source=WorkflowSource(id='case'))",
    ],
)
def test_path_reexports_cannot_write_or_mask_transforms(body: str) -> None:
    source = _source(body).replace(
        "from vibecomfy.workflow import VibeWorkflow, WorkflowSource",
        "from vibecomfy.templates import Path\nfrom vibecomfy.workflow import VibeWorkflow, WorkflowSource",
    )
    admission = simulate.admit_template_source(source)
    assert admission.status == "unsupported"
    assert admission.reason is not None
    assert admission.reason["code"] == "forbidden_import_name"


@pytest.mark.parametrize(
    "body",
    [
        "    inspect.sys.modules['os'].system('true')\n    return VibeWorkflow(id='case', source=WorkflowSource(id='case'))",
        "    inspect.sys.modules['builtins'].eval('1')\n    return VibeWorkflow(id='case', source=WorkflowSource(id='case'))",
        "    inspect.sys.modules['subprocess'].run(['true'])\n    return VibeWorkflow(id='case', source=WorkflowSource(id='case'))",
        "    fd = int(inspect.sys.argv[6])\n    inspect.sys.modules['os'].write(fd, b'CORRUPT')\n    return VibeWorkflow(id='case', source=WorkflowSource(id='case'))",
    ],
)

def test_inspect_reexport_cannot_reach_process_or_protocol(body: str) -> None:
    source = _source(body).replace(
        "from vibecomfy.workflow import VibeWorkflow, WorkflowSource",
        "from vibecomfy.templates import inspect\nfrom vibecomfy.workflow import VibeWorkflow, WorkflowSource",
    )
    admission = simulate.admit_template_source(source)
    assert admission.status == "unsupported"
    assert admission.reason is not None
    assert admission.reason["code"] == "forbidden_import_name"

def test_path_write_and_source_read_attacks_never_execute(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = tmp_path / "path-attack-marker"
    source = _source(
        f"    Path({str(marker)!r}).write_text('PATH_HIT')\n"
        "    source_length = len(Path(__file__).read_text())\n"
        "    return VibeWorkflow(id='case', source=WorkflowSource(id='case'))"
    ).replace(
        "from vibecomfy.workflow import VibeWorkflow, WorkflowSource",
        "from vibecomfy.templates import Path\nfrom vibecomfy.workflow import VibeWorkflow, WorkflowSource",
    )
    _corpus(Path(tmp_path / "unsafe.py"), monkeypatch)
    unsafe_path = Path(tmp_path / "unsafe.py")
    unsafe_path.write_text(source + "\n# _set_id_map(\n", encoding="utf-8")

    result = simulate.simulate_rule("drop_set_id_map=true", ["image/case"])

    assert result.status == "unsupported"
    assert result.per_template[0]["changed"] is True
    assert result.per_template[0]["unsupported"]["reason"]["code"] == "forbidden_import_name"
    assert not marker.exists()


@pytest.mark.parametrize(
    "operation",
    [
        "system({marker!r}, 'INSPECT_OS')",
        "eval(f\"open({marker!r}, 'w').write('INSPECT_EVAL')\")",
        "run(['sh', '-c', f\"printf SUBPROCESS > {marker!s}\"])",
    ],
)
def test_inspect_process_attacks_never_execute(
    operation: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = tmp_path / "inspect-attack-marker"
    if operation.startswith("system"):
        body = f"    inspect.sys.modules['os'].{operation.format(marker=str(marker))}\n"
    elif operation.startswith("eval"):
        body = f"    inspect.sys.modules['builtins'].{operation.format(marker=str(marker))}\n"
    else:
        body = f"    inspect.sys.modules['subprocess'].{operation.format(marker=str(marker))}\n"
    source = _source(
        body + "    return VibeWorkflow(id='case', source=WorkflowSource(id='case'))"
    ).replace(
        "from vibecomfy.workflow import VibeWorkflow, WorkflowSource",
        "from vibecomfy.templates import inspect\nfrom vibecomfy.workflow import VibeWorkflow, WorkflowSource",
    )
    unsafe_path = tmp_path / "unsafe.py"
    unsafe_path.write_text(source, encoding="utf-8")
    _corpus(unsafe_path, monkeypatch)

    result = simulate.simulate_rule("drop_set_id_map=true", ["image/case"])

    assert result.status == "unsupported"
    assert result.per_template[0]["unsupported"]["reason"]["code"] == "forbidden_import_name"
    assert not marker.exists()

@pytest.mark.parametrize(
    ("statement", "code"),
    [
        ("from vibecomfy.templates import Path as benign", "forbidden_import_name"),
        ("from vibecomfy.templates import ReadyMetadata as inspect", "forbidden_import_alias"),
        ("from vibecomfy.nodes.core import LoadImage as open", "forbidden_import_alias"),
    ],
)
def test_import_aliases_cannot_relabel_admitted_or_reexported_names(
    statement: str, code: str
) -> None:
    source = _source().replace(
        "from vibecomfy.workflow import VibeWorkflow, WorkflowSource",
        statement + "\nfrom vibecomfy.workflow import VibeWorkflow, WorkflowSource",
    )
    admission = simulate.admit_template_source(source)
    assert admission.status == "unsupported"
    assert admission.reason is not None
    assert admission.reason["code"] == code


def test_worker_transport_has_no_protocol_fd_in_argv_or_pass_fds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "safe.py"
    path.write_text(_source(), encoding="utf-8")
    observed: list[tuple[list[str], dict[str, object]]] = []
    original_popen = simulate.subprocess.Popen

    def capture(command, **kwargs):
        observed.append((list(command), dict(kwargs)))
        return original_popen(command, **kwargs)

    monkeypatch.setattr(simulate.subprocess, "Popen", capture)
    result = simulate._run_artifact_worker(path, logical_path=Path("/logical/template.py"))
    assert result["ok"] is True
    assert observed
    command, kwargs = observed[0]
    assert "--protocol-fd" not in command
    assert "pass_fds" not in kwargs


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
