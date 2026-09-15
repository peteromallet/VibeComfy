from __future__ import annotations

import argparse

import pytest

from vibecomfy.cli import build_parser


@pytest.mark.parametrize(
    "argv",
    [
        ["--yes", "import", "workflow.json"],
        ["-y", "import", "workflow.json"],
        ["import", "workflow.json", "--yes"],
        ["--non-interactive", "import", "workflow.json"],
        ["import", "workflow.json", "--non-interactive"],
        ["analyze", "--yes", "info", "workflow.json"],
        ["analyze", "info", "workflow.json", "--yes"],
        ["analyze", "--non-interactive", "info", "workflow.json"],
        ["analyze", "info", "workflow.json", "--non-interactive"],
        ["templates", "--yes", "create", "bundle", "--id", "image/demo", "--out", "demo.py"],
        ["templates", "create", "bundle", "--id", "image/demo", "--out", "demo.py", "--yes"],
        ["templates", "--non-interactive", "create", "bundle", "--id", "image/demo", "--out", "demo.py"],
        ["templates", "create", "bundle", "--id", "image/demo", "--out", "demo.py", "--non-interactive"],
        ["--yes", "analyze", "info", "workflow.json", "--non-interactive"],
    ],
)
def test_security_flags_parse_at_root_nested_and_leaf_positions(argv: list[str]) -> None:
    args = build_parser().parse_args(argv)

    assert getattr(args, "assume_yes", False) is ("--yes" in argv or "-y" in argv)
    assert getattr(args, "non_interactive", False) is ("--non-interactive" in argv)


def test_local_runpod_yes_and_config_yes_keep_their_destinations() -> None:
    parser = build_parser()

    runpod = parser.parse_args(["runpod", "terminate", "pod-123", "--yes"])
    assert runpod.yes is True
    assert not getattr(runpod, "assume_yes", False)

    config = parser.parse_args(["config", "init", "--yes"])
    assert config.assume_yes is True


def test_root_yes_survives_nested_parsers_in_main(monkeypatch: pytest.MonkeyPatch) -> None:
    import vibecomfy.cli as cli

    parser = build_parser()

    def replace_funcs(current: argparse.ArgumentParser) -> None:
        current.set_defaults(func=lambda args: 0)
        for action in current._actions:
            if isinstance(action, argparse._SubParsersAction):
                for child in action.choices.values():
                    replace_funcs(child)

    replace_funcs(parser)
    monkeypatch.setattr(cli, "build_parser", lambda: parser)
    monkeypatch.setattr(cli, "_maybe_print_nudge", lambda args: None)
    captured = []
    monkeypatch.setattr(cli, "set_gate_context", captured.append)

    assert cli.main(["--yes", "analyze", "info", "workflow.json", "--non-interactive"]) == 0
    assert captured[0].assume_yes is True
    assert captured[0].non_interactive is True
