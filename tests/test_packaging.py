from __future__ import annotations

import tomllib
from pathlib import Path


def test_top_level_public_api_exports_promised_names() -> None:
    import vibecomfy
    from vibecomfy.ingest.loader import load_template, load_workflow_json
    from vibecomfy.registry.library import workflow_from_template
    from vibecomfy.runtime.run import run_embedded, run_embedded_sync

    expected = {
        "load_workflow_json": load_workflow_json,
        "load_template": load_template,
        "workflow_from_template": workflow_from_template,
        "run_embedded": run_embedded,
        "run_embedded_sync": run_embedded_sync,
    }

    for name, value in expected.items():
        assert getattr(vibecomfy, name) is value
        assert name in vibecomfy.__all__


def test_nodes_package_layout_stays_collapsed() -> None:
    nodes_dir = Path("vibecomfy/nodes")

    assert not (nodes_dir / "_generated").exists()
    assert sorted(path.relative_to(nodes_dir).as_posix() for path in nodes_dir.rglob("*.pyi")) == []


def test_runpod_dependencies_stay_out_of_core_metadata() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]

    core_dependencies = project["dependencies"]
    runpod_dependencies = project["optional-dependencies"]["runpod-local"]

    assert "python-dotenv>=1.0" not in core_dependencies
    assert "python-dotenv>=1.0" in runpod_dependencies
    assert not any("file://" in dependency or "/Users/" in dependency for dependency in runpod_dependencies)
    assert any(
        dependency == "runpod-lifecycle @ git+https://github.com/banodoco/runpod-lifecycle.git@v0.1.1"
        for dependency in runpod_dependencies
    )


def test_agent_extra_uses_validated_arnold_ref() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]

    agent_dependencies = project["optional-dependencies"]["agent"]

    assert agent_dependencies == [
        "arnold @ git+https://github.com/peteromallet/Arnold.git@9d8b2a4af93ba764e7e82381656a8fffb3678cf7"
    ]
    assert not any("3db60a6cfe73e250b836d6147952ccf449151906" in dependency for dependency in agent_dependencies)


def test_unused_schema_dependencies_stay_out_of_core_metadata() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]

    assert "pydantic>=2" not in project["dependencies"]


def test_web_dist_excluded_from_wheel_and_sdist() -> None:
    hatch = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["tool"]["hatch"]
    web_dist_pattern = "/vibecomfy/comfy_nodes/web_dist/**"

    wheel = hatch["build"]["targets"]["wheel"]
    assert web_dist_pattern in wheel["exclude"]

    sdist = hatch["build"]["targets"]["sdist"]
    assert web_dist_pattern in sdist["exclude"]
