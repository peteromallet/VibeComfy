"""Pytest config for the Node Resolution Epic acceptance suite.

Registers the per-sprint markers so `pytest -m sprint_a` works without warnings.
This is the *spec* suite (skipped gates); shipped tests land in `tests/`.
"""


def pytest_configure(config):
    for sprint in ("a", "b", "c"):
        config.addinivalue_line(
            "markers",
            f"sprint_{sprint}: acceptance gate that must pass after Sprint "
            f"{sprint.upper()} (see testing.md).",
        )
