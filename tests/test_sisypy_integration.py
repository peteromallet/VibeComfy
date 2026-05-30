from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

# These tests exercise the optional sibling ``sisypy`` package (an editable
# install of the neighbouring ``../sisypy`` checkout). When it is not installed,
# the module skips rather than fails — matching VibeComfy's optional-dependency
# test convention (the ``[comfy]`` / ``[png]`` extras).
pytest.importorskip("sisypy")


def test_vibecomfy_loads_sibling_sisypy_package_layout():
    import sisypy
    from sisypy import Boulder, Push, cli, compare
    from sisypy.runner import load_scenario, render_brief, run_all

    package_file = Path(sisypy.__file__).resolve()

    assert package_file.parent.name == "sisypy"
    assert package_file.parent.parent.name == "sisypy"
    assert cli is sisypy.cli
    assert compare is sisypy.compare
    assert Boulder is sisypy.Scenario
    assert Push is sisypy.ActorRun
    assert callable(run_all)
    assert callable(load_scenario)
    assert render_brief("hello ${name}", {"name": "vibecomfy"}) == "hello vibecomfy"


def test_sisypy_schema_contracts_used_by_vibecomfy_round_trip():
    from sisypy.schema import ActorRun, RunMode, ScenarioOutcome, SuccessProofLevel

    first = ActorRun(id="first")
    second = ActorRun(id="second")

    first.extras["consumer"] = {"name": "vibecomfy"}
    first.mode = RunMode.STRUCTURAL
    first.success_proof_level = SuccessProofLevel.VALIDATED
    first.outcome = ScenarioOutcome.FAKE_NO_OP

    payload = json.loads(json.dumps(dataclasses.asdict(first)))

    assert second.extras == {}
    assert payload["extras"] == {"consumer": {"name": "vibecomfy"}}
    assert payload["mode"] == "structural"
    assert payload["success_proof_level"] == "validated"
    assert payload["outcome"] == "fake_no_op"
    assert ScenarioOutcome(payload["outcome"]) is ScenarioOutcome.FAKE_NO_OP


def test_sisypy_public_cli_helper_is_embeddable(capsys):
    from sisypy import FakeProjectAdapter, build_cli_parser, cli

    parser = build_cli_parser(FakeProjectAdapter())
    help_text = parser.format_help()

    assert "--verbose" in help_text
    assert "--capture-interval-sec" in help_text

    with pytest.raises(SystemExit) as exc_info:
        cli(FakeProjectAdapter(), argv=["--help"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 0
    assert "usage:" in captured.out


def test_sisypy_private_runner_import_guard():
    runner = Path("tests/test_sisypy_integration.py")
    private_import = "from sisypy.runner import " + "_"
    private_cli = "_cli" + "_entry_point"
    private_parser = "_build" + "_arg_parser"

    assert runner.is_file()
    text = runner.read_text(encoding="utf-8")
    assert private_import not in text
    assert private_cli not in text
    assert private_parser not in text
