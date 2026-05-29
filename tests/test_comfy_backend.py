"""Tests for vibecomfy.comfy_backend (T9).

The comfy backend is an OPTIONAL adoption hook (SD2). ensure_nodes() must be
memoized and must never raise — when the [comfy] extra or the vendor/ComfyUI
submodule is unavailable, callers fall back to the pure-Python path. These tests
skip gracefully (i.e. assert the fallback) when the backend is unavailable.
"""
from __future__ import annotations

import pytest

from vibecomfy import comfy_backend


@pytest.fixture(autouse=True)
def _reset_backend_cache():
    comfy_backend.reset_cache()
    yield
    comfy_backend.reset_cache()


def test_ensure_nodes_never_raises_and_returns_bool():
    """ensure_nodes() returns a bool and never raises, regardless of availability."""
    result = comfy_backend.ensure_nodes()
    assert isinstance(result, bool)


def test_ensure_nodes_is_memoized(monkeypatch):
    """The import attempt happens at most once; repeated calls hit the cache."""
    calls = {"n": 0}
    real_vendor_on_path = comfy_backend._vendor_on_path

    def _counting():
        calls["n"] += 1
        real_vendor_on_path()

    monkeypatch.setattr(comfy_backend, "_vendor_on_path", _counting)

    first = comfy_backend.ensure_nodes()
    second = comfy_backend.ensure_nodes()
    third = comfy_backend.ensure_nodes()

    assert first == second == third
    # _vendor_on_path runs only on the first (uncached) call.
    assert calls["n"] == 1


def test_fallback_to_pure_python_when_backend_unavailable(monkeypatch):
    """When the comfy import is forced to fail, ensure_nodes() returns False.

    This is the pure-Python fallback contract: an absent extra / uninitialized
    submodule yields False without error, exactly like the real-world skip case.
    """
    import builtins

    real_import = builtins.__import__

    def _blocked_import(name, *args, **kwargs):
        if name == "comfy" or name.startswith("comfy."):
            raise ImportError("comfy backend unavailable (simulated)")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocked_import)
    comfy_backend.reset_cache()

    assert comfy_backend.ensure_nodes() is False


def test_reset_cache_allows_recompute(monkeypatch):
    comfy_backend.reset_cache()
    assert comfy_backend._ENSURE_CACHE is None
    comfy_backend.ensure_nodes()
    assert comfy_backend._ENSURE_CACHE is not None
    comfy_backend.reset_cache()
    assert comfy_backend._ENSURE_CACHE is None
