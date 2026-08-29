from __future__ import annotations

import pathlib

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


def test_quarantine_retirement_workflow_is_documented() -> None:
    readme = (pathlib.Path(__file__).parent / "README.md").read_text(encoding="utf-8")

    assert "Quarantine Retirement" in readme
    assert "tests/quarantine/" in readme
    assert "pytest tests/test_comfy_nodes_browser.py tests/test_quarantine_loader.py tests/test_quarantine_policy.py tests/characterization/test_known_failures_audit.py -q" in readme
    assert "pytest --known-failures-audit -q" in readme
