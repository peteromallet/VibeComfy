from __future__ import annotations

from pathlib import Path

pytest_plugins = ("vibecomfy.testing._pytest_plugin",)

import vibecomfy.testing as testing
from vibecomfy.handles import Handle
from vibecomfy.runtime.session import RunResult
from vibecomfy.workflow import VibeWorkflow


def test_testing_api_exports_required_names() -> None:
    for name in (
        "vibecomfy_workflow_factory",
        "vibecomfy_handle_factory",
        "dry_runtime",
        "make_workflow_factory",
        "make_handle_factory",
    ):
        assert hasattr(testing, name)


def test_testing_api_star_import_exposes_required_names() -> None:
    namespace: dict[str, object] = {}
    exec("from vibecomfy.testing import *", namespace)

    for name in (
        "vibecomfy_workflow_factory",
        "vibecomfy_handle_factory",
        "dry_runtime",
        "make_workflow_factory",
        "make_handle_factory",
    ):
        assert name in namespace


def test_testing_plugin_exports_required_fixture_names() -> None:
    from vibecomfy.testing import _pytest_plugin

    assert _pytest_plugin.vibecomfy_workflow_factory is testing.vibecomfy_workflow_factory
    assert _pytest_plugin.vibecomfy_handle_factory is testing.vibecomfy_handle_factory
    assert _pytest_plugin.dry_runtime is testing.dry_runtime
    assert _pytest_plugin.make_workflow_factory is testing.make_workflow_factory
    assert _pytest_plugin.make_handle_factory is testing.make_handle_factory


def test_factory_helpers_create_workflow_and_handle() -> None:
    workflow = testing.make_workflow_factory()("demo")
    handle = testing.make_handle_factory()("42", 1, "IMAGE", "image")

    assert isinstance(workflow, VibeWorkflow)
    assert workflow.id == "demo"
    assert workflow.source.source_type == "test"
    assert handle == Handle("42", 1, output_type="IMAGE", name="image")


def test_exported_factories_do_not_raise_not_implemented() -> None:
    workflow_factory = testing.make_workflow_factory()
    handle_factory = testing.make_handle_factory()

    assert workflow_factory("not-implemented-check").id == "not-implemented-check"
    assert handle_factory("7") == Handle("7")


def test_pytest_fixtures_are_available(
    vibecomfy_workflow_factory: testing.WorkflowFactory,
    vibecomfy_handle_factory: testing.HandleFactory,
    dry_runtime: testing.DryRuntime,
) -> None:
    workflow = vibecomfy_workflow_factory("fixture-demo")
    first = workflow.node("EmptyLatentImage", width=64, height=64, batch_size=1).out(0)
    save = workflow.node("SaveImage", images=first).out(0)
    handle = vibecomfy_handle_factory(save.node_id, save.output_slot, name="saved")

    result = dry_runtime.run_sync(workflow)

    assert isinstance(handle, Handle)
    assert isinstance(result, RunResult)
    assert Path(result.metadata_path).is_file()
    assert dry_runtime.prompts[-1]["2"]["inputs"]["images"] == ["1", 0]
