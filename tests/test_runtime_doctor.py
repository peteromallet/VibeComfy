from __future__ import annotations

from pathlib import Path

from vibecomfy.commands.runtime import build_runtime_doctor_payload


def test_runtime_doctor_reports_missing_local_runtime_but_present_libraries(monkeypatch):
    monkeypatch.setattr(
        "vibecomfy.commands.runtime._detected_comfy_install",
        lambda: (None, None),
    )
    monkeypatch.setattr(
        "vibecomfy.commands.runtime.resolve",
        lambda slot: type(
            "Resolution",
            (),
            {
                "state": type("State", (), {"name": "SET"})(),
                "path": Path("/tmp/vibecomfy-doctor-missing-library"),
                "source": "global",
            },
        )(),
    )

    payload = build_runtime_doctor_payload()

    assert payload["status"] == "ok"
    assert payload["readiness_status"] == "not_ready"
    assert payload["readiness"]["embedded"]["status"] == "not_ready"
    assert payload["readiness"]["managed"]["status"] == "not_ready"
    assert payload["readiness"]["external"]["status"] == "unverified"
    assert payload["local_library"]["models"]["exists"] is False
    assert any("configured model/node libraries do not make embedded runtime ready" in m for m in payload["messages"])


def test_runtime_doctor_accepts_a_real_comfy_root(monkeypatch, tmp_path: Path):
    (tmp_path / "server.py").touch()
    (tmp_path / "nodes.py").touch()
    monkeypatch.setattr(
        "vibecomfy.commands.runtime._detected_comfy_install",
        lambda: (tmp_path, tmp_path / "models"),
    )
    monkeypatch.setattr(
        "vibecomfy.commands.runtime.resolve",
        lambda slot: type(
            "Resolution",
            (),
            {"state": type("State", (), {"name": "UNSET"})(), "path": None, "source": "default"},
        )(),
    )

    payload = build_runtime_doctor_payload()

    assert payload["readiness_status"] == "ready"
    assert payload["readiness"]["embedded"]["status"] == "ready"
    assert payload["readiness"]["managed"]["status"] == "ready"
