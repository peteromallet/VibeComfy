"""Provenance paths must not require a checkout (an installed wheel has none)."""
from pathlib import Path

from vibecomfy import utils
from vibecomfy.errors import CheckoutRequiredError


def test_repo_relative_path_without_a_checkout(monkeypatch, tmp_path):
    def no_checkout():
        raise CheckoutRequiredError("no checkout")

    monkeypatch.setattr(utils, "find_repo_root", no_checkout)
    assert utils.repo_relative_path("source.json") == "source.json"
    absolute = tmp_path / "flow.json"
    assert utils.repo_relative_path(absolute) == str(absolute.resolve())
    assert Path(utils.repo_relative_path(str(absolute))).is_absolute()


def test_template_metadata_without_a_checkout(monkeypatch):
    from vibecomfy import templates

    def no_checkout():
        raise CheckoutRequiredError("no checkout")

    monkeypatch.setattr(templates, "_repo_root", no_checkout)
    assert templates._coverage_manifest_row("any/template") == {}
    assert templates._project_version()  # the installed package's version, not an error
    assert isinstance(templates._comfy_core_metadata(), dict)
