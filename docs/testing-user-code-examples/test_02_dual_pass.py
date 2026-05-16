"""Test for example 2."""
from vibecomfy.testing import assert_compiles_cleanly, dry_run
from docs.testing_user_code_examples.example_02 import build as build_02  # noqa: E402


def test_dual_pass_compiles():
    wf = build_02()
    assert_compiles_cleanly(wf)


def test_dry_run_reports_nodes():
    result = dry_run(build_02())
    assert result.would_invoke
