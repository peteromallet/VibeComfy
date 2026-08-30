from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest


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
    lifecycle_ref = (
        "runpod-lifecycle @ git+https://github.com/banodoco/runpod-lifecycle.git@"
        "14d12f3c5e100247ffb1360c8fe6ba82aa5c7aa6"
    )
    assert runpod_dependencies == ["python-dotenv>=1.0", lifecycle_ref]
    assert project["optional-dependencies"]["runpod-launch"] == [
        "python-dotenv>=1.0",
        lifecycle_ref,
    ]


def test_agent_extra_uses_validated_arnold_ref() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]

    agent_dependencies = project["optional-dependencies"]["agent"]

    assert agent_dependencies == [
        "arnold @ git+https://github.com/peteromallet/Arnold.git@9d8b2a4af93ba764e7e82381656a8fffb3678cf7"
    ]
    assert not any("3db60a6cfe73e250b836d6147952ccf449151906" in dependency for dependency in agent_dependencies)


def test_arnold_is_extra_only() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]

    assert not any(dependency.startswith("arnold ") for dependency in project["dependencies"])
    assert any(dependency.startswith("arnold @ git+") for dependency in project["optional-dependencies"]["agent"])


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


@pytest.fixture(scope="module")
def installed_wheel(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """Build and install a wheel into an isolated, no-dependency venv."""
    build_check = subprocess.run(
        [sys.executable, "-m", "build", "--version"],
        capture_output=True,
        text=True,
    )
    if build_check.returncode != 0:
        pytest.skip("the wheel-build regression requires the `build` package")

    root = tmp_path_factory.mktemp("wheel-install")
    wheel_dir = root / "wheel"
    wheel_dir.mkdir()
    built = subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(wheel_dir), "--no-isolation"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    wheels = sorted(wheel_dir.glob("vibecomfy-*.whl"))
    assert len(wheels) == 1

    # Put the venv inside a checkout-shaped directory.  The installed package
    # must still refuse checkout-only corpus access: its direct package-layout
    # candidate is site-packages, not this ancestor checkout.
    clone_dir = root / "clone"
    clone_dir.mkdir()
    (clone_dir / "pyproject.toml").write_text(
        "[project]\nname = 'vibecomfy'\n",
        encoding="utf-8",
    )
    venv_dir = clone_dir / ".venv"
    created = subprocess.run(
        [sys.executable, "-m", "venv", "--system-site-packages", str(venv_dir)],
        capture_output=True,
        text=True,
    )
    assert created.returncode == 0, created.stdout + created.stderr
    venv_python = venv_dir / "bin" / "python"
    if os.name == "nt":
        venv_python = venv_dir / "Scripts" / "python.exe"
    installed = subprocess.run(
        [str(venv_python), "-m", "pip", "install", "--no-deps", "--disable-pip-version-check", str(wheels[0])],
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert installed.returncode == 0, installed.stdout + installed.stderr
    return venv_python, wheels[0]


def _install_wheel_in_venv(wheel: Path, venv_dir: Path) -> Path:
    created = subprocess.run(
        [sys.executable, "-m", "venv", "--system-site-packages", str(venv_dir)],
        capture_output=True,
        text=True,
    )
    assert created.returncode == 0, created.stdout + created.stderr
    venv_python = venv_dir / "bin" / "python"
    if os.name == "nt":
        venv_python = venv_dir / "Scripts" / "python.exe"
    installed = subprocess.run(
        [str(venv_python), "-m", "pip", "install", "--no-deps", "--disable-pip-version-check", str(wheel)],
        cwd=venv_dir.parent,
        capture_output=True,
        text=True,
    )
    assert installed.returncode == 0, installed.stdout + installed.stderr
    return venv_python


@pytest.mark.timeout(180)
def test_wheel_isolated_import_cli_plugin_and_corpus_failure(
    installed_wheel: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    venv_python, _wheel = installed_wheel
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}

    imports = subprocess.run(
        [
            str(venv_python),
            "-c",
            "import vibecomfy; from vibecomfy import VibeWorkflow, image, video; import vibecomfy.comfy_nodes; print(vibecomfy.__file__); print(VibeWorkflow.__name__)",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert imports.returncode == 0, imports.stdout + imports.stderr
    package_file = Path(imports.stdout.splitlines()[0]).resolve()
    assert package_file.is_relative_to(venv_python.parents[1].resolve())
    assert "VibeWorkflow" in imports.stdout

    help_result = subprocess.run(
        [str(venv_python), "-m", "vibecomfy.cli", "--help"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert help_result.returncode == 0, help_result.stdout + help_result.stderr
    assert "usage: vibecomfy" in help_result.stdout

    corpus = subprocess.run(
        [
            str(venv_python),
            "-c",
            "from vibecomfy.registry.ready import workflow_from_ready; workflow_from_ready('image/z_image')",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert corpus.returncode != 0
    assert "git checkout" in corpus.stderr
    assert "pip install -e ." in corpus.stderr


def test_wheel_does_not_trust_spoofed_ancestor_pyproject(
    installed_wheel: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    _installed_python, wheel = installed_wheel
    spoofed_root = tmp_path / "spoofed-ancestor"
    spoofed_root.mkdir()
    (spoofed_root / "pyproject.toml").write_text(
        "[project]\nname = 'vibecomfy'\n",
        encoding="utf-8",
    )
    spoofed_python = _install_wheel_in_venv(wheel, spoofed_root / ".venv")
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}

    result = subprocess.run(
        [
            str(spoofed_python),
            "-c",
            "import vibecomfy; from vibecomfy.utils import find_repo_root; print(vibecomfy.__file__); find_repo_root()",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode != 0
    package_file = Path(result.stdout.splitlines()[0]).resolve()
    assert package_file.is_relative_to(spoofed_python.parents[1].resolve())
    assert "CheckoutRequiredError" in result.stderr
    assert "git checkout" in result.stderr


def test_wheel_metadata_keeps_arnold_under_agent_extra(installed_wheel: tuple[Path, Path]) -> None:
    venv_python, _wheel = installed_wheel
    result = subprocess.run(
        [
            str(venv_python),
            "-c",
            "import importlib.metadata as m; print(*m.metadata('vibecomfy').get_all('Requires-Dist'), sep='\\n')",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    requirements = result.stdout.splitlines()
    assert not any(line == "arnold" or line.startswith("arnold ") and "extra == 'agent'" not in line for line in requirements)
    assert any("arnold @ git+https://github.com/peteromallet/Arnold.git@9d8b2a4af93ba764e7e82381656a8fffb3678cf7" in line and "extra == 'agent'" in line for line in requirements)
