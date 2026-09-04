from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import vibecomfy.cli_loader as cli_loader
from vibecomfy.cli_loader import load_bundle, load_workflow_any
from vibecomfy.security.provenance import Provenance
from vibecomfy.workflow_bundle import WorkflowBundleError


def test_load_workflow_any_accepts_basename_ready_id() -> None:
    workflow = load_workflow_any("z_image")

    assert workflow.metadata["ready_template"] == "image/z_image"


def test_load_workflow_any_accepts_slash_ready_id() -> None:
    workflow = load_workflow_any("video/wan_t2v")

    assert workflow.metadata["ready_template"] == "video/wan_t2v"


def test_load_workflow_any_accepts_scratchpad_path(tmp_path: Path) -> None:
    scratchpad = tmp_path / "scratch.py"
    scratchpad.write_text(
        "from vibecomfy.workflow import VibeWorkflow, WorkflowSource\n\n"
        "def build():\n"
        "    wf = VibeWorkflow('scratch', WorkflowSource('scratch'))\n"
        "    wf.add_node('SaveImage', images='placeholder')\n"
        "    return wf.finalize_metadata()\n",
        encoding="utf-8",
    )

    workflow = load_workflow_any(str(scratchpad))

    assert workflow.id == "scratch"
    assert workflow.outputs[0].output_type == "SaveImage"


def test_load_workflow_any_accepts_json_path(tmp_path: Path) -> None:
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text(
        json.dumps({"1": {"class_type": "Integer", "inputs": {"value": 7}}}),
        encoding="utf-8",
    )

    workflow = load_workflow_any(str(workflow_path))

    assert workflow.id == "workflow"
    assert workflow.nodes["1"].class_type == "Integer"


@pytest.mark.parametrize("suffix", [".py", ".json"])
def test_direct_file_loading_does_not_require_ready_discovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, suffix: str
) -> None:
    path = tmp_path / f"workflow{suffix}"
    if suffix == ".py":
        path.write_text(
            "from vibecomfy.workflow import VibeWorkflow, WorkflowSource\n\n"
            "def build():\n"
            "    return VibeWorkflow('direct', WorkflowSource('direct'))\n",
            encoding="utf-8",
        )
    else:
        path.write_text(
            json.dumps({"1": {"class_type": "Integer", "inputs": {"value": 7}}}),
            encoding="utf-8",
        )

    def unavailable() -> None:
        raise RuntimeError("ready discovery unavailable")

    monkeypatch.setattr(cli_loader, "ready_template_discovery", unavailable)

    workflow = load_workflow_any(str(path))

    assert workflow.id == ("direct" if suffix == ".py" else "workflow")


def test_load_workflow_any_missing_id_raises_key_error() -> None:
    with pytest.raises(KeyError):
        load_workflow_any("not_a_real_workflow_id")


def test_load_workflow_any_missing_path_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_workflow_any(str(tmp_path / "missing.json"))


def test_load_bundle_is_distinct_from_bare_compatibility_loader(tmp_path: Path) -> None:
    source = tmp_path / "bundle.py"
    source.write_text(
        "from vibecomfy.workflow import VibeWorkflow, WorkflowSource\n\n"
        "def build():\n"
        "    return VibeWorkflow('bundle', WorkflowSource('bundle'))\n",
        encoding="utf-8",
    )

    bundle = load_bundle(source, trust=Provenance.USER_CONFIRMED)

    assert bundle.workflow.id == "bundle"
    assert bundle.workflow_identity == "bundle"
    assert bundle.ui_digest == ""


def test_load_bundle_imported_json_uses_offline_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import vibecomfy.schema as schema

    source = tmp_path / "imported.json"
    source.write_text(
        json.dumps(
            {
                "workflow_id": "imported",
                "prompt": {"1": {"class_type": "Integer", "inputs": {"value": 7}}},
            }
        ),
        encoding="utf-8",
    )

    def fail_auto(*args, **kwargs):
        raise AssertionError("auto schema provider must not be used by load_bundle")

    monkeypatch.setattr(schema, "get_schema_provider", fail_auto)
    bundle = load_bundle(source)

    assert bundle.workflow_identity == "imported"


def test_load_bundle_imported_api_preserves_reserved_node_ids(tmp_path: Path) -> None:
    source = tmp_path / "reserved.json"
    source.write_text(
        json.dumps(
            {
                "workflow_id": "reserved",
                "source": {"class_type": "Integer", "inputs": {"value": 7}},
            }
        ),
        encoding="utf-8",
    )

    bundle = load_bundle(source)

    assert "source" in bundle.workflow.nodes


def test_load_bundle_prompt_identity_does_not_strip_inner_reserved_node(tmp_path: Path) -> None:
    source = tmp_path / "prompt.json"
    source.write_text(
        json.dumps(
            {
                "workflow_id": "prompted",
                "prompt": {
                    "source": {"class_type": "Integer", "inputs": {"value": 7}},
                },
            }
        ),
        encoding="utf-8",
    )

    bundle = load_bundle(source)

    assert bundle.workflow_identity == "prompted"
    assert "source" in bundle.workflow.nodes


def test_load_bundle_rejects_ambiguous_reserved_api_mapping(tmp_path: Path) -> None:
    source = tmp_path / "ambiguous.json"
    source.write_text(
        json.dumps({"workflow_id": "ambiguous", "source": {"not": "an identity"}}),
        encoding="utf-8",
    )

    with pytest.raises(WorkflowBundleError, match="ambiguous API envelope"):
        load_bundle(source)


def test_load_bundle_accepts_only_explicit_ephemeral_workflow() -> None:
    from vibecomfy.workflow import VibeWorkflow, WorkflowSource

    workflow = VibeWorkflow("ephemeral", WorkflowSource("ephemeral"))
    bundle = load_bundle(workflow)

    assert bundle.python_path is None
    assert bundle.provenance == {"operation": "ephemeral"}


def test_production_inspection_enters_bundle_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    """A production inspection helper must not fall back to the bare loader."""
    from types import SimpleNamespace

    from vibecomfy.commands import analyze
    from vibecomfy.workflow import VibeWorkflow, WorkflowSource

    workflow = VibeWorkflow("inspection", WorkflowSource("inspection"))
    bundle = SimpleNamespace(workflow=workflow)

    monkeypatch.setattr(analyze, "load_bundle", lambda reference: bundle)
    monkeypatch.setattr(
        cli_loader,
        "load_workflow_any",
        lambda *_args, **_kwargs: pytest.fail("bare compatibility loader was used"),
    )

    assert analyze._load_workflow("inspection") is workflow


def test_run_command_blocks_bare_runtime_after_bundle_compile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T13 must fail closed until the T14 approved-record transport exists."""
    from vibecomfy.commands import run as run_command
    from vibecomfy.workflow import VibeWorkflow, WorkflowSource

    workflow = VibeWorkflow("run-boundary", WorkflowSource("run-boundary"))
    calls: list[str] = []

    class Bundle:
        def __init__(self) -> None:
            self.workflow = workflow

        def compile(self, **kwargs):
            calls.append("compile")
            return object()

    monkeypatch.setattr(run_command, "load_bundle", lambda *_args, **_kwargs: Bundle())
    monkeypatch.setattr(run_command, "get_schema_provider", lambda *_args, **_kwargs: object())
    args = run_command.argparse.Namespace(
        path="run-boundary",
        runtime="embedded",
        server_url=None,
        memory_profile=None,
        prompt=None,
        seed=None,
        steps=None,
    )

    assert run_command._cmd_run(args) == 1
    assert calls == ["compile"]


def test_run_binds_public_inputs_without_mutating_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.commands import run as run_command

    class Workflow:
        id = "run-inputs"
        inputs = {"prompt": object(), "seed": object(), "steps": object()}

        def set_prompt(self, value):
            raise AssertionError("run must not mutate prompt")

        def set_seed(self, value):
            raise AssertionError("run must not mutate seed")

        def set_steps(self, value):
            raise AssertionError("run must not mutate steps")

    calls: list[dict[str, object]] = []

    class Bundle:
        workflow = Workflow()

        def compile(self, **kwargs):
            calls.append(kwargs)
            return object()

    monkeypatch.setattr(run_command, "load_bundle", lambda *_args, **_kwargs: Bundle())
    monkeypatch.setattr(run_command, "get_schema_provider", lambda *_args, **_kwargs: object())
    args = argparse.Namespace(
        path="run-inputs",
        runtime="embedded",
        server_url=None,
        backend="api",
        ready=False,
        memory_profile=None,
        ensure_packs=False,
        ensure_models=None,
        shared_models_root=None,
        quiet_schema_degradation=False,
        prompt="new prompt",
        seed=17,
        steps=23,
    )

    assert run_command._cmd_run(args) == 1
    assert calls[0]["run_inputs"] == {"prompt": "new prompt", "seed": 17, "steps": 23}


def test_run_preserves_parser_options_and_server_preflight() -> None:
    from vibecomfy.cli import build_parser

    args = build_parser().parse_args(
        [
            "run",
            "source.py",
            "--runtime",
            "server",
            "--server-url",
            "http://example.invalid",
            "--backend",
            "api",
            "--prompt",
            "p",
            "--seed",
            "3",
            "--steps",
            "4",
            "--memory-profile",
            "2",
            "--ensure-packs",
            "--no-ensure-models",
            "--shared-models-root",
            "/models",
            "--quiet-schema-degradation",
        ]
    )

    assert args.func.__module__ == "vibecomfy.commands.run"
    assert args.backend == "api"
    assert args.ensure_models is False
    assert args.shared_models_root == "/models"


def test_raw_run_failure_prints_safe_port_actions(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from vibecomfy.commands import run as run_command

    monkeypatch.setattr(
        run_command,
        "load_bundle",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("legacy source")),
    )
    monkeypatch.setattr(run_command, "get_schema_provider", lambda *_args, **_kwargs: object())

    code = run_command._cmd_run(
        argparse.Namespace(
            path="/tmp/a workflow.json",
            runtime="auto",
            server_url=None,
            memory_profile=None,
            ensure_packs=False,
        )
    )

    assert code == 1
    output = capsys.readouterr().err
    assert "vibecomfy port check '/tmp/a workflow.json' --json" in output
    assert "vibecomfy port convert '/tmp/a workflow.json' --out 'out/scratchpads/a workflow.py'" in output


def test_validation_mints_one_approval_record_and_no_schema_stays_compat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.commands import validate as validate_command
    from vibecomfy.workflow import ValidationReport

    class Workflow:
        id = "validation"

        def validate(self, **_kwargs):
            return ValidationReport(ok=True, issues=[])

    class Bundle:
        workflow = Workflow()

        def __init__(self):
            self.compiles = 0

        def compile(self, **_kwargs):
            self.compiles += 1
            return object()

    bundle = Bundle()
    monkeypatch.setattr(validate_command, "load_bundle", lambda *_args, **_kwargs: bundle)
    monkeypatch.setattr(validate_command, "get_schema_provider", lambda *_args, **_kwargs: object())

    assert validate_command._cmd_validate(argparse.Namespace(path="x", json=False, no_schema=False)) == 0
    assert bundle.compiles == 1

    no_schema_bundle = Bundle()
    monkeypatch.setattr(validate_command, "load_bundle", lambda *_args, **_kwargs: no_schema_bundle)
    monkeypatch.setattr(
        validate_command,
        "get_schema_provider",
        lambda *_args, **_kwargs: pytest.fail("--no-schema must not build a provider"),
    )
    assert validate_command._cmd_validate(argparse.Namespace(path="x", json=False, no_schema=True)) == 0
    assert no_schema_bundle.compiles == 0


def test_image_op_approves_copy_then_fails_without_artifact(monkeypatch: pytest.MonkeyPatch) -> None:
    from vibecomfy.ops import image
    from vibecomfy.router import RouterResult

    class Workflow:
        inputs = {"prompt": object()}
        touched = False

        def copy(self):
            return type(self)()

    class Patch:
        def apply(self, workflow):
            workflow.touched = True

    class Bundle:
        def __init__(self, workflow):
            self.workflow = workflow
            self.compiles: list[dict[str, object]] = []

        def compile(self, **kwargs):
            self.compiles.append(kwargs)
            return object()

    workflow = Workflow()
    original = Bundle(workflow)
    approved = Bundle(workflow)
    monkeypatch.setattr(image, "pick", lambda *_args, **_kwargs: RouterResult("template", [Patch()], []))
    bundles = iter([original, approved])
    monkeypatch.setattr(image, "load_bundle", lambda *_args, **_kwargs: next(bundles))

    with pytest.raises(RuntimeError, match="T14 runtime boundary"):
        image._t2i("prompt")
    assert approved.compiles[0]["run_inputs"] == {"prompt": "prompt"}
    assert original.workflow.touched is False


def test_runtime_eval_and_queue_guards_fail_before_legacy_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.commands import runtime

    monkeypatch.setattr(runtime, "load_bundle", lambda *_args, **_kwargs: SimpleNamespace(workflow=object()))
    monkeypatch.setattr(runtime, "get_schema_provider", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(runtime, "compile_eval_subgraph", lambda *_args: pytest.fail("eval compiled before handoff"))
    code = runtime._cmd_runtime_eval_node(
        argparse.Namespace(path="workflow.py", node="1", server_url=None, runtime="embedded")
    )
    assert code == 2
    with pytest.raises(RuntimeError, match="T16-owned"):
        asyncio.run(runtime._queue_embedded({}))
    with pytest.raises(RuntimeError, match="T16-owned"):
        asyncio.run(runtime._queue_server({}, "http://example.invalid"))


def test_warm_smoke_retains_two_records_and_never_starts_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = Path(__file__).resolve().parents[1] / "scripts" / "warm_session_smoke.py"
    spec = importlib.util.spec_from_file_location("warm_session_smoke_t13", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class Bundle:
        def __init__(self):
            self.compiles = 0

        def compile(self, **_kwargs):
            self.compiles += 1
            return object()

    bundles = [Bundle(), Bundle()]
    monkeypatch.setattr(module, "get_schema_provider", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(module, "load_bundle", lambda *_args, **_kwargs: bundles.pop(0))
    with pytest.raises(RuntimeError, match="T14 runtime boundary"):
        asyncio.run(module._run(argparse.Namespace(first="one", second="two")))
    assert not bundles


def test_router_loader_is_selection_only(monkeypatch: pytest.MonkeyPatch) -> None:
    import vibecomfy.cli_loader as loader
    from vibecomfy.router import _core

    workflow = object()
    monkeypatch.setattr(loader, "load_bundle", lambda *_args, **_kwargs: SimpleNamespace(workflow=workflow))
    assert _core._default_workflow_loader("template") is workflow
