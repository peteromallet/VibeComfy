from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Sequence

from vibecomfy._git_utils import git_head, git_stdout
from vibecomfy._graph_utils import UI_ONLY_CLASS_TYPES, is_api_link, node_id_sort_key


def test_ui_only_class_types_matches_legacy_strip_set() -> None:
    assert UI_ONLY_CLASS_TYPES == frozenset({"Note", "MarkdownNote"})


def test_is_api_link_accepts_legacy_numeric_and_string_list_links() -> None:
    assert is_api_link([1, 0])
    assert is_api_link(["1", 0])
    assert is_api_link(["1", "slot"])


def test_is_api_link_rejects_bad_shapes() -> None:
    assert not is_api_link(None)
    assert not is_api_link({"node": "1", "slot": 0})
    assert not is_api_link(["1"])
    assert not is_api_link(["1", 0, "extra"])
    assert not is_api_link(["abc", 0])
    assert not is_api_link(["", 0])


def test_is_api_link_can_allow_tuple_links() -> None:
    assert not is_api_link(("1", 0))
    assert is_api_link(("1", 0), allow_tuple=True)


def test_is_api_link_can_preserve_schema_style_string_source_ids() -> None:
    assert is_api_link(
        ("source_node", 0),
        allow_tuple=True,
        require_string_node_id=True,
        require_numeric_node_id=False,
        require_int_slot=True,
    )


def test_is_api_link_strict_string_node_id_rejects_numeric_source_ids() -> None:
    assert not is_api_link([1, 0], require_string_node_id=True)
    assert is_api_link(["1", 0], require_string_node_id=True)


def test_is_api_link_strict_int_slot_rejects_non_int_slots() -> None:
    assert not is_api_link(["1", "0"], require_int_slot=True)
    assert is_api_link(["1", 0], require_int_slot=True)


def test_is_api_link_can_allow_compound_numeric_node_ids() -> None:
    assert not is_api_link(["76:67", 0])
    assert is_api_link(["76:67", 0], allow_compound_node_id=True, require_int_slot=True)
    assert not is_api_link(["76:abc", 0], allow_compound_node_id=True)


def test_is_api_link_tool_mode_is_string_source_strict_with_compound_ids() -> None:
    tool_mode = {
        "allow_tuple": False,
        "require_string_node_id": True,
        "require_numeric_node_id": True,
        "allow_compound_node_id": True,
        "require_int_slot": True,
    }

    assert not is_api_link([1, 0], **tool_mode)
    assert is_api_link(["1", 0], **tool_mode)
    assert is_api_link(["76:67", 0], **tool_mode)
    assert not is_api_link(["76:67", "0"], **tool_mode)


def test_workflow_helpers_is_api_link_narrowing_rejects_string_and_float_slots() -> None:
    # The old body used int(value[1]) coercion, accepting "3" and 3.5.
    # The new body uses isinstance(slot, int) via require_int_slot=True, narrowing both to False.
    # first_link_input and resolve_compile_link_value only see real compiled API links
    # where slots are always ints, so the narrowing is safe.
    from vibecomfy._workflow_helpers import is_api_link as wh_is_api_link, first_link_input
    from vibecomfy._helper_resolve import resolve_compile_link_value

    # Narrowed: string slot and float slot now rejected
    assert not wh_is_api_link(["abc", "3"])
    assert not wh_is_api_link(["abc", 3.5])

    # first_link_input: these non-link values are skipped, not returned as links
    assert first_link_input({"a": ["abc", "3"]}) is None
    assert first_link_input({"a": ["abc", 3.5]}) is None

    # resolve_compile_link_value: non-link values are passed through unchanged
    assert resolve_compile_link_value(["abc", "3"], {}, {}) == ["abc", "3"]
    assert resolve_compile_link_value(["abc", 3.5], {}, {}) == ["abc", 3.5]


def test_node_id_sort_key_orders_numeric_ids_before_text() -> None:
    assert sorted(["10", "2", "abc"], key=node_id_sort_key) == ["2", "10", "abc"]


def test_node_id_sort_key_orders_compound_ids_when_allowed() -> None:
    assert sorted(["77", "76:67", "2", "76:5"], key=lambda value: node_id_sort_key(value, allow_compound=True)) == [
        "2",
        "76:5",
        "76:67",
        "77",
    ]


def test_node_id_sort_key_treats_compound_ids_as_tail_when_disallowed() -> None:
    assert sorted(["76:67", "10", "2"], key=lambda value: node_id_sort_key(value, allow_compound=False)) == [
        "2",
        "10",
        "76:67",
    ]


class FakeGitRunner:
    def __init__(self, *, stdout: str = "abc123\n", fail: bool = False) -> None:
        self.stdout = stdout
        self.fail = fail
        self.calls: list[tuple[list[str], bool, bool, bool]] = []

    def __call__(
        self,
        args: Sequence[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        call = list(args)
        self.calls.append((call, check, capture_output, text))
        if self.fail:
            raise subprocess.CalledProcessError(1, call, stderr="boom")
        return subprocess.CompletedProcess(call, 0, stdout=self.stdout, stderr="")


def test_git_stdout_uses_injected_runner_and_returns_stdout() -> None:
    runner = FakeGitRunner(stdout="dirty\n")

    assert git_stdout(Path("/tmp/pack"), ["status", "--porcelain"], runner=runner) == "dirty\n"
    assert runner.calls == [
        (["git", "-C", "/tmp/pack", "status", "--porcelain"], True, True, True),
    ]


def test_git_head_uses_injected_runner_and_strips_stdout() -> None:
    runner = FakeGitRunner(stdout="abc123\n")

    assert git_head(Path("/tmp/pack"), runner=runner) == "abc123"
    assert runner.calls == [
        (["git", "-C", "/tmp/pack", "rev-parse", "HEAD"], True, True, True),
    ]


def test_git_helpers_return_none_on_failed_git_calls() -> None:
    runner = FakeGitRunner(fail=True)

    assert git_stdout(Path("/tmp/pack"), ["rev-parse", "HEAD"], runner=runner) is None
    assert git_head(Path("/tmp/pack"), runner=runner) is None


def test_git_stdout_resolves_subprocess_run_inside_function(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(args: Sequence[str], *, check: bool, capture_output: bool, text: bool) -> subprocess.CompletedProcess[str]:
        calls.append(list(args))
        assert check is True
        assert capture_output is True
        assert text is True
        return subprocess.CompletedProcess(args, 0, stdout="abc123\n", stderr="")

    monkeypatch.setattr("vibecomfy._git_utils.subprocess.run", fake_run)

    assert git_head(Path("/tmp/pack")) == "abc123"
    assert calls == [["git", "-C", "/tmp/pack", "rev-parse", "HEAD"]]
