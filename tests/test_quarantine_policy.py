from __future__ import annotations

import pathlib
from types import SimpleNamespace

import pytest

from tests import conftest as test_conftest


def _write_quarantine(path: pathlib.Path, body: str) -> None:
    path.write_text(
        "# owner: quarantine-policy\n"
        "# reason: exercises quarantine policy gates\n"
        f"{body}\n",
        encoding="utf-8",
    )


def test_quarantine_policy_rejects_malformed_and_overbroad_entries(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    quarantine_dir = tmp_path / "quarantine"
    quarantine_dir.mkdir()
    monkeypatch.setattr(test_conftest, "_QUARANTINE_DIR", quarantine_dir)
    monkeypatch.setattr(test_conftest, "_KNOWN_FAILURES_FILE", tmp_path / "known_failures.txt")

    malformed = quarantine_dir / "malformed.txt"
    _write_quarantine(malformed, "tests/test_example.py")
    with pytest.raises(ValueError, match="not a pytest nodeid"):
        test_conftest._load_quarantine_index()

    malformed.unlink()
    overbroad = quarantine_dir / "overbroad.txt"
    _write_quarantine(overbroad, "tests/test_example.py::TestExample")
    with pytest.raises(ValueError, match="too broad"):
        test_conftest._load_quarantine_index()


def test_known_failures_txt_must_remain_comment_only(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    known_failures = tmp_path / "known_failures.txt"
    known_failures.write_text(
        "# legacy file is documentation only\n"
        "tests/test_comfy_nodes_browser.py::test_browser_harness_smoke\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(test_conftest, "_KNOWN_FAILURES_FILE", known_failures)

    with pytest.raises(ValueError, match="active legacy known-failure entries are not allowed"):
        test_conftest._assert_known_failures_file_is_retired()


def test_quarantine_summary_policy_includes_file_and_owner() -> None:
    source = pathlib.Path(test_conftest.__file__).read_text(encoding="utf-8")

    assert "TOLERATED FAIL: {nodeid} [{entry.display_path}; owner={entry.owner}]" in source


def test_quarantine_summary_never_masks_test_errors(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    known_nodeid = "tests/test_known.py::test_known"
    entry = test_conftest.QuarantineEntry(
        nodeid=known_nodeid,
        path=tmp_path / "known.txt",
        owner="quarantine-policy",
        reason="test",
        metadata={"owner": "quarantine-policy", "reason": "test"},
    )
    monkeypatch.setattr(test_conftest, "_load_quarantine_index", lambda: {known_nodeid: entry})

    class Reporter:
        stats = {
            "failed": [SimpleNamespace(nodeid=known_nodeid)],
            "error": [SimpleNamespace(nodeid="tests/test_error.py::test_error")],
        }
        _session = SimpleNamespace(exitstatus=1)
        messages: list[str] = []

        def write_sep(self, *_args: object, **_kwargs: object) -> None:
            return None

        def write_line(self, message: str, **_kwargs: object) -> None:
            self.messages.append(message)

    reporter = Reporter()
    config = SimpleNamespace(getoption=lambda *_args, **_kwargs: False)

    test_conftest.pytest_terminal_summary(reporter, exitstatus=0, config=config)

    assert any("TEST ERROR: tests/test_error.py::test_error" in message for message in reporter.messages)

def test_quarantine_retirement_workflow_is_documented() -> None:
    readme = (pathlib.Path(__file__).parent / "README.md").read_text(encoding="utf-8")

    assert "Quarantine Retirement" in readme
    assert "tests/quarantine/" in readme
    assert "pytest tests/test_comfy_nodes_browser.py tests/test_quarantine_loader.py tests/test_quarantine_policy.py tests/characterization/test_known_failures_audit.py -q" in readme
    assert "pytest --known-failures-audit -q" in readme
